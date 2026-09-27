#!/usr/bin/env python3
"""
Build every generated page and region of the Cleanzit site.

    python3 tools/build_site.py

Sources (edit these, never the generated output):
  data/prices.json      every price, offer and membership plan
  data/services.json    service pages  -> services/<slug>/
  data/bhopal.json      outlets, zones, areas -> bhopal/, bhopal/<area>/
  content/guides/*.html guides         -> guides/, guides/<slug>/

Also rewrites the <!-- BEGIN:gen:NAME --> ... <!-- END:gen:NAME --> regions in
the hand-written pages (nav + footer on all six; price panels, structured data
and estimator on pricing.html; service cards on services.html; outlets on
stores.html; areas/services/outlets on index.html) and in llms.txt, and
regenerates sitemap.xml. Standard library only; deterministic, so re-running
with unchanged sources changes nothing. Generated folders are pruned of pages
whose source was removed.
"""
import datetime
import html
import json
import os
import re
import shutil
import sys
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = "https://www.cleanzit.co.in"
PHONE_ORDERS = "917777818187"
PHONE_ORDERS_DISPLAY = "+91 77778 18187"
PHONE_CALL = "917777818188"
PHONE_CALL_DISPLAY = "+91 77778 18188"
EMAIL = "franchise@cleanzit.in"
STATIC_PAGES = ["index.html", "about.html", "services.html", "pricing.html", "stores.html", "contact.html"]
NAV = [("About", "/about.html"), ("Services", "/services.html"), ("Pricing", "/pricing.html"),
       ("Areas", "/bhopal/"), ("Guides", "/guides/"), ("Stores", "/stores.html"), ("Contact", "/contact.html")]
ORG_REF = {"@type": "Organization", "@id": f"{BASE}/#organization", "name": "Cleanzit", "url": f"{BASE}/"}

e = html.escape


def load(path):
    with open(os.path.join(ROOT, path), encoding="utf-8") as f:
        return json.load(f)


def write(path, text):
    full = os.path.join(ROOT, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as f:
        f.write(text)


def slugify(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def wa_link(text):
    return f"https://wa.me/{PHONE_ORDERS}?text=" + urllib.parse.quote(text)


def fail(msg):
    sys.exit("build_site: " + msg)


# ============================================================ prices
class Prices:
    """Resolves price references from data/prices.json.

    ITEM:COLUMN  -> a price-list cell, e.g. shirt:dry
    home:ID      -> a home-service offer
    Values are strings like "60" or "72+" ('+' = starting from)."""

    def __init__(self, data):
        self.data = data
        self.facts = data["facts"]
        self.items, self.cat_of = {}, {}
        for cat in data["categories"]:
            for it in cat["items"]:
                if it["id"] in self.items:
                    fail(f"duplicate price id {it['id']}")
                self.items[it["id"]] = it
                self.cat_of[it["id"]] = cat
        self.home = {h["id"]: h for h in data["home_services"]["items"]}
        self.offer_on = bool(data["home_services"].get("label"))

    @staticmethod
    def rupees(v, plus=None):
        v = str(v)
        n = int(v.rstrip("+"))
        if plus is None:
            plus = v.endswith("+")
        return f"₹{n:,}" + ("+" if plus else "")

    @staticmethod
    def num(v):
        return int(str(v).rstrip("+"))

    def cell(self, ref):
        """-> dict(label, short_label, value, display, num, plus, unit, kind)"""
        if ref.startswith("home:"):
            h = self.home.get(ref[5:]) or fail(f"unknown home service {ref}")
            unit = h.get("unit", "")
            return {"label": f"{h['name']} (at home)", "short_label": h["name"], "value": h["now"],
                    "display": self.rupees(h["now"], True) + (f" / {unit}" if unit else ""),
                    "num": self.num(h["now"]), "plus": True, "unit": unit, "kind": "home", "item": h}
        iid, _, col = ref.partition(":")
        it = self.items.get(iid) or fail(f"unknown price item {ref}")
        v = it.get(col)
        if not v:
            fail(f"price {ref} is empty")
        cat = self.cat_of[iid]
        multi = len(cat["columns"]) > 1
        label = it["name"] + (f" — {cat['columns'][col].lower()}" if multi else "")
        unit = it.get("unit", "")
        return {"label": label, "short_label": it["name"], "value": v,
                "display": self.rupees(v) + (f" / {unit}" if unit else ""),
                "num": self.num(v), "plus": v.endswith("+"), "unit": unit, "kind": "item", "item": it}

    def fill(self, text):
        def sub(m):
            kind, arg = m.group(1), m.group(2)
            if kind == "fact":
                return self.facts.get(arg) or fail(f"unknown fact {arg}")
            if kind == "p":
                return self.rupees(self.cell(arg)["value"])
            h = self.home.get(arg) or fail(f"unknown home service {arg}")
            return self.rupees(h["now" if kind == "now" else "was"], False)
        out = re.sub(r"\{(p|now|was|fact):([^}]+)\}", sub, text)
        if re.search(r"\{(p|now|was|fact):", out):
            fail(f"unresolved placeholder in: {text[:60]}")
        return out

    def offer_ld(self, c):
        o = {"@type": "Offer", "name": c["label"], "priceCurrency": "INR", "price": str(c["num"])}
        if c["unit"] or c["plus"]:
            spec = {"@type": "UnitPriceSpecification", "price": c["num"], "priceCurrency": "INR"}
            if c["unit"]:
                spec["unitText"] = c["unit"]
            if c["plus"]:
                spec["minPrice"] = c["num"]
            o["priceSpecification"] = spec
        return o


# ============================================================ shared fragments
def nav_items(active, indent):
    li = []
    for name, href in NAV:
        cls = ' class="active"' if href == active else ""
        li.append(f'{indent}<li><a href="{href}"{cls}>{name}</a></li>')
    li.append(f'{indent}<li><a href="tel:+{PHONE_CALL}" class="nav-phone">📞 {PHONE_CALL_DISPLAY}</a></li>')
    return "\n".join(li)


def footer_cols(ctx, indent):
    svc = ctx["services_by_slug"]
    s_links = "\n".join(f'{indent}            <li><a href="/services/{sl}/">{e(svc[sl]["name"])}</a></li>' for sl in ctx["services"]["footer"])
    a_links = "\n".join(f'{indent}            <li><a href="/bhopal/{slugify(n)}/">Laundry in {e(n)}</a></li>' for n in ctx["bhopal"]["footer_areas"])
    main = next(o for o in ctx["bhopal"]["outlets"] if o.get("main"))
    return f'''{indent}<div class="footer-col">
{indent}    <h4>Cleanzit</h4>
{indent}    <p>Laundry, dry cleaning &amp; home cleaning in Bhopal — and India's happiest laundry franchise.</p>
{indent}    <ul>
{indent}        <li><a href="/about.html">About Us</a></li>
{indent}        <li><a href="/pricing.html">Pricing</a></li>
{indent}        <li><a href="/stores.html">Stores</a></li>
{indent}        <li><a href="/guides/">Guides</a></li>
{indent}        <li><a href="/contact.html">Contact</a></li>
{indent}    </ul>
{indent}</div>
{indent}<div class="footer-col">
{indent}    <h4>Services in Bhopal</h4>
{indent}    <ul>
{s_links}
{indent}            <li><a href="/services.html">All services →</a></li>
{indent}    </ul>
{indent}</div>
{indent}<div class="footer-col">
{indent}    <h4>Laundry in Bhopal</h4>
{indent}    <ul>
{a_links}
{indent}            <li><a href="/bhopal/">All {len(ctx["bhopal"]["areas"])} areas →</a></li>
{indent}    </ul>
{indent}</div>
{indent}<div class="footer-col">
{indent}    <h4>Contact Us</h4>
{indent}    <ul>
{indent}        <li><a href="tel:+{PHONE_ORDERS}">{PHONE_ORDERS_DISPLAY}</a> (pickups &amp; WhatsApp)</li>
{indent}        <li><a href="tel:+{PHONE_CALL}">{PHONE_CALL_DISPLAY}</a></li>
{indent}        <li><a href="mailto:{EMAIL}">{EMAIL}</a></li>
{indent}        <li>{e(full_address(main))}</li>
{indent}    </ul>
{indent}</div>'''


def ld_script(obj, indent="    "):
    body = json.dumps(obj, indent=2, ensure_ascii=False)
    return f'{indent}<script type="application/ld+json">\n' + "\n".join(indent + l for l in body.splitlines()) + f"\n{indent}</script>"


def breadcrumb_ld(trail):
    return {"@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": i + 1, "name": n, "item": u} for i, (n, u) in enumerate(trail)]}


def crumbs_html(trail):
    parts = [f'<a href="{u.replace(BASE, "") or "/"}">{e(n)}</a>' for n, u in trail[:-1]] + [e(trail[-1][0])]
    return '<p class="lp-crumbs">' + " › ".join(parts) + "</p>"


def faq_block(qas):
    items = "\n".join(f'    <details>\n        <summary>{e(q)}</summary>\n        <p>{e(a)}</p>\n    </details>' for q, a in qas)
    return f'<div class="lp-faq">\n{items}\n</div>'


def faq_ld(qas, url):
    return {"@type": "FAQPage", "@id": url + "#faq", "mainEntity": [
        {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in qas]}


def steps_html(ctx, mode="pickup"):
    f = ctx["prices"].facts
    if mode == "home":
        steps = [("Book a visit", "WhatsApp or call us and pick a date and time slot."),
                 ("We come to you", "Our home-services team cleans at your place."),
                 ("Enjoy a fresh home", "Pay once the job is done.")]
    else:
        steps = [("Book a pickup", "WhatsApp or call us with a time that suits you."),
                 ("We collect &amp; clean", "We pick up from your door; every item is tagged, inspected and cleaned by fabric."),
                 (f"Delivered in {f['delivery_days']} days", f"Cleaned, finished and packed — free pickup &amp; delivery on orders above ₹{f['free_pickup_min']}.")]
    li = "\n".join(f"    <li><strong>{t}</strong><span>{d}</span></li>" for t, d in steps)
    return f'<ol class="lp-steps">\n{li}\n</ol>'


def price_rows_table(ctx, refs, caption):
    P = ctx["prices"]
    rows = "\n".join(f'            <tr><th scope="row">{e(c["label"])}</th><td>{e(c["display"])}</td></tr>' for c in (P.cell(r) for r in refs))
    return f'''<div class="lp-prices">
    <table>
        <caption class="sr-only">{e(caption)}</caption>
        <tbody>
{rows}
        </tbody>
    </table>
</div>'''


def home_offer_table(ctx, ids, caption):
    P = ctx["prices"]
    hs = P.data["home_services"]
    rows = []
    for hid in ids:
        h = P.home[hid]
        unit = f" / {h['unit']}" if h["unit"] else ""
        if P.offer_on and h["was"] != h["now"]:
            val = f'<del>{P.rupees(h["was"], False)}{unit}</del> <strong>{P.rupees(h["now"], False)}{unit}</strong>'
        else:
            val = f"{P.rupees(h['now'], True)}{unit}"
        rows.append(f'            <tr><th scope="row">{e(h["name"])} (at home)</th><td>{val}</td></tr>')
    label = f'<p class="lp-offer-tag">🪔 {e(hs["label"])} — starting prices</p>' if P.offer_on else ""
    return f'''{label}<div class="lp-prices">
    <table>
        <caption class="sr-only">{e(caption)}</caption>
        <tbody>
{chr(10).join(rows)}
        </tbody>
    </table>
</div>'''


def outlet_card(o, closest=False, heading="h3"):
    classes = "lp-outlet" + (" is-main" if o.get("main") else "") + (" is-closest" if closest else "")
    tag = "Closest to you" if closest else ("Main store" if o.get("main") else "Outlet")
    if closest and o.get("main"):
        tag += " · Main store"
    return f'''<div class="{classes}">
    <span class="lp-tag">{e(tag)}</span>
    <{heading}>{e(o["name"])}</{heading}>
    <address>{e(full_address(o))}</address>
    <div class="lp-outlet-links">
        <a href="{e(maps_link(o))}" target="_blank" rel="noopener">Directions &amp; timings</a>
        <a class="wa" href="{e(wa_link("Hi Cleanzit, I'd like to book a pickup from your " + o["short"] + " outlet."))}" target="_blank" rel="noopener">WhatsApp</a>
        <a href="tel:+{PHONE_ORDERS}">Call</a>
    </div>
</div>'''


def full_address(o):
    pin = f" {o['postalCode']}" if o.get("postalCode") else ""
    return f"{o['street']}, Bhopal, Madhya Pradesh{pin}"


def maps_link(o):
    return "https://www.google.com/maps/search/?api=1&query=" + urllib.parse.quote(
        f"Cleanzit Dry Clean & Laundry Service, {o['street']}, Bhopal")


def outlet_ld(o):
    addr = {"@type": "PostalAddress", "streetAddress": o["street"], "addressLocality": "Bhopal",
            "addressRegion": "Madhya Pradesh", "addressCountry": "IN"}
    if o.get("postalCode"):
        addr["postalCode"] = o["postalCode"]
    return {"@type": ["DryCleaningOrLaundry", "LocalBusiness"], "@id": f"{BASE}/#outlet-{o['id']}",
            "name": o["name"], "url": f"{BASE}/stores.html", "telephone": "+91-7777818187",
            "image": f"{BASE}/assets/logo.png", "priceRange": "₹15 – ₹1,599", "currenciesAccepted": "INR",
            "address": addr, "hasMap": maps_link(o), "areaServed": {"@type": "City", "name": "Bhopal"},
            "parentOrganization": ORG_REF}


def area_groups(ctx, per_zone=None):
    B = ctx["bhopal"]
    out = []
    for zone in B["zones"]:
        areas = [a for a in B["areas"] if a["zone"] == zone][:per_zone]
        chips = "\n".join(f'        <a href="/bhopal/{slugify(a["name"])}/">Laundry in {e(a["name"])}</a>' for a in areas)
        out.append(f'<div class="lp-area-group">\n    <h3>{e(zone)}</h3>\n    <div class="lp-chips">\n{chips}\n    </div>\n</div>')
    return "\n".join(out)


def service_chips(ctx, slugs=None, label_fn=lambda s: s["name"]):
    svc = ctx["services"]["services"] if slugs is None else [ctx["services_by_slug"][x] for x in slugs]
    return "\n".join(f'    <a href="/services/{s["slug"]}/">{s["icon"]} {e(label_fn(s))}</a>' for s in svc)


def service_start(ctx, s):
    """Lowest price across a service's price refs and home offers -> (display, num) or None."""
    P = ctx["prices"]
    if s.get("start"):
        c = P.cell(s["start"])
    else:
        cells = [P.cell(r) for r in s["prices"]] + [P.cell("home:" + h) for h in s.get("home", [])]
        if not cells:
            return None
        c = min(cells, key=lambda c: c["num"])
    return f"₹{c['num']:,}" + (f" / {c['unit']}" if c["unit"] else ""), c["num"]


def clamp_desc(*parts, limit=160):
    """Join description parts, dropping trailing optional parts until it fits
    the length search engines display (~160 chars)."""
    parts = list(parts)
    while len(parts) > 1 and len(" ".join(parts)) > limit:
        parts.pop()
    return " ".join(parts)


def page_shell(ctx, *, title, description, canonical, body, ld, active, og_type="website"):
    lds = "\n".join(ld_script(b) for b in ld)
    return f'''<!DOCTYPE html>
<html lang="en-IN">

<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <!-- Generated by tools/build_site.py — edit data/ or content/, not this file. -->
    <title>{e(title)}</title>
    <meta name="description" content="{e(description)}">
    <link rel="canonical" href="{canonical}">
    <meta name="robots" content="index, follow, max-image-preview:large, max-snippet:-1">
    <meta name="geo.region" content="IN-MP">
    <meta name="geo.placename" content="Bhopal, Madhya Pradesh">
    <meta property="og:type" content="{og_type}">
    <meta property="og:site_name" content="Cleanzit">
    <meta property="og:locale" content="en_IN">
    <meta property="og:title" content="{e(title)}">
    <meta property="og:description" content="{e(description)}">
    <meta property="og:url" content="{canonical}">
    <meta property="og:image" content="{BASE}/assets/india_laundry_hero.png">
    <meta name="twitter:card" content="summary_large_image">
    <link rel="icon" href="/assets/logo.png" type="image/png">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700;800&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="/css/styles.css">
{lds}
</head>

<body>

    <script src="/js/offers-banner.js"></script>
    <noscript>
        <div class="offer-banner" style="position:static; height:auto; padding:0.6rem 1rem; white-space:normal;">
            20% OFF your first order &middot; FREE pickup &amp; delivery above &#8377;300 &middot;
            Call <a href="tel:+917777818187">77778 18187</a>
        </div>
    </noscript>

    <header>
        <div class="container">
            <a href="/" class="logo">
                <img src="/assets/logo.png" alt="Cleanzit Logo" style="height: 60px;" width="178" height="60">
            </a>
            <div class="mobile-toggle" aria-label="Toggle Navigation">☰</div>
            <nav>
                <ul class="nav-links">
{nav_items(active, "                    ")}
                </ul>
            </nav>
        </div>
    </header>

    <main>
{body}
    </main>

    <footer>
        <div class="container">
            <div class="footer-content">
{footer_cols(ctx, "                ")}
            </div>
            <div class="footer-bottom">
                <p>&copy; 2026 Cleanzit India. All rights reserved.</p>
            </div>
        </div>
    </footer>

    <a href="https://wa.me/{PHONE_ORDERS}?text=Hi," class="whatsapp-float" target="_blank" rel="noopener noreferrer" aria-label="Chat on WhatsApp">
        <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z" /></svg>
    </a>

    <script src="/js/app.js"></script>
</body>

</html>
'''


def section(inner, alt=False, id_=None):
    cls = " alt" if alt else ""
    idattr = f' id="{id_}"' if id_ else ""
    return (f'        <section class="lp-section{cls}"{idattr}>\n'
            f'            <div class="container">\n{inner}\n            </div>\n        </section>')


def hero(trail, h1_html, lede, ctas):
    return f'''        <section class="lp-hero">
            <div class="container">
                {crumbs_html(trail)}
                <h1>{h1_html}</h1>
                <p class="lp-lede">{lede}</p>
                <div class="lp-ctas">
{ctas}
                </div>
            </div>
        </section>'''


def cta_pair(wa_text, wa_label):
    return (f'                    <a class="btn" href="{e(wa_link(wa_text))}" target="_blank" rel="noopener">💬 {e(wa_label)}</a>\n'
            f'                    <a class="btn btn-outline" href="tel:+{PHONE_ORDERS}">📞 Call {PHONE_ORDERS_DISPLAY}</a>')


# ============================================================ service pages
def build_service(ctx, s):
    P = ctx["prices"]
    fill = P.fill
    url = f"{BASE}/services/{s['slug']}/"
    trail = [("Home", BASE + "/"), ("Services", BASE + "/services.html"), (s["h1"], url)]
    start = service_start(ctx, s)
    start_txt = f"Starting {start[0]}" if start else "Ask us for a quote"
    intro = "\n".join(f"                <p>{e(fill(p))}</p>" for p in s["intro"])
    includes = "\n".join(f"                    <li>{e(fill(i))}</li>" for i in s["includes"])
    tips = "\n".join(f"                    <li>{e(fill(t))}</li>" for t in s["tips"])
    qas = [(fill(q), fill(a)) for q, a in s["faqs"]]
    prices_parts = []
    if s["prices"]:
        prices_parts.append(price_rows_table(ctx, s["prices"], f"{s['h1']} prices"))
    if s.get("home"):
        prices_parts.append(home_offer_table(ctx, s["home"], f"{s['h1']} at home prices"))
    price_section = ""
    if prices_parts:
        price_section = section(f'''                <h2>{e(s["name"])} Prices in Bhopal</h2>
                <p class="lp-sub">A “+” means starting price — the final rate depends on fabric and condition. <a href="/pricing.html">Full price list →</a></p>
''' + "\n".join(prices_parts))
    guide = ""
    if s.get("guide"):
        g = ctx["guides_by_slug"][s["guide"]]
        guide = f'\n                <p class="lp-center">📖 Read our guide: <a href="/guides/{g["slug"]}/">{e(g["h1"])}</a></p>'
    zones = ", ".join(ctx["bhopal"]["zones"])
    at_home = s.get("mode") == "home"
    logistics = "anywhere in Bhopal" if at_home else f"free pickup &amp; delivery above ₹{P.facts['free_pickup_min']}"
    body = "\n\n".join(part for part in [
        hero(trail, e(s["h1"]), f'{e(fill(s["short"]))} {e(start_txt)} · {logistics} · {P.facts["first_order_off"]}% off your first order.',
             cta_pair(f"Hi Cleanzit, I'd like to book {s['name'].lower()} in Bhopal.", "Book on WhatsApp")),
        section(f'''                <h2>About Our {e(s["name"])} Service</h2>
                <div class="lp-article">
{intro}
                <h3>What's included</h3>
                <ul class="lp-checks">
{includes}
                </ul>
                </div>''', alt=True),
        price_section,
        section(f'''                <h2>How It Works</h2>
{steps_html(ctx, s.get("mode", "pickup"))}''', alt=True),
        section(f'''                <h2>{e(s["tips_title"])}</h2>
                <div class="lp-article">
                <ul class="lp-checks">
{tips}
                </ul>
                </div>{guide}'''),
        section(f'''                <h2>Frequently Asked Questions</h2>
{faq_block(qas)}''', alt=True),
        section(f'''                <h2>Related Services</h2>
                <div class="lp-chips">
{service_chips(ctx, s["related"])}
                </div>
                <p class="lp-sub" style="margin-top:1.5rem;">Available across Bhopal — {e(zones)}. <a href="/bhopal/">Find your area →</a></p>'''),
    ] if part)
    offers = [P.offer_ld(P.cell(r)) for r in s["prices"]] + [P.offer_ld(P.cell("home:" + h)) for h in s.get("home", [])]
    svc_ld = {"@type": "Service", "@id": url + "#service", "name": s["h1"], "serviceType": s["name"],
              "description": fill(s["short"]), "url": url, "provider": ORG_REF,
              "areaServed": {"@type": "City", "name": "Bhopal"}}
    if offers:
        svc_ld["hasOfferCatalog"] = {"@type": "OfferCatalog", "name": f"{s['name']} prices", "itemListElement": offers}
    ld = [{"@context": "https://schema.org", "@graph": [breadcrumb_ld(trail), svc_ld, faq_ld(qas, url)]}]
    desc = clamp_desc(f"{fill(s['short'])} {start_txt}.", "At your home in Bhopal." if at_home else f"Free pickup above ₹{P.facts['free_pickup_min']} in Bhopal.",
                      f"{P.facts['first_order_off']}% off your first order.")
    return page_shell(ctx, title=fill(s["title"]), description=desc, canonical=url, body=body, ld=ld, active="/services.html")


def build_services_redirect():
    """/services/ has no page of its own (the hub is /services.html); send visitors there."""
    return f'''<!DOCTYPE html>
<html lang="en-IN">
<head>
    <meta charset="UTF-8">
    <!-- Generated by tools/build_site.py -->
    <title>Cleanzit Services</title>
    <link rel="canonical" href="{BASE}/services.html">
    <meta name="robots" content="noindex, follow">
    <meta http-equiv="refresh" content="0; url=/services.html">
</head>
<body><p><a href="/services.html">Cleanzit services</a></p></body>
</html>
'''


# ============================================================ guides
def load_guides(prices):
    gdir = os.path.join(ROOT, "content", "guides")
    guides = []
    for fn in sorted(os.listdir(gdir)):
        if not fn.endswith(".html"):
            continue
        raw = open(os.path.join(gdir, fn), encoding="utf-8").read()
        m = re.match(r"\s*<!--meta\s*(\{.*?\})\s*-->\s*", raw, re.S)
        if not m:
            fail(f"content/guides/{fn}: missing <!--meta {{...}} --> header")
        meta = json.loads(m.group(1))
        meta["slug"] = fn[:-5]
        meta["html"] = prices.fill(raw[m.end():].strip())
        guides.append(meta)
    return guides


def build_guide(ctx, g):
    url = f"{BASE}/guides/{g['slug']}/"
    trail = [("Home", BASE + "/"), ("Guides", BASE + "/guides/"), (g["h1"], url)]
    body_html = "\n".join("                " + l for l in g["html"].splitlines())
    parts = [
        hero(trail, e(g["h1"]), e(g["description"]),
             cta_pair("Hi Cleanzit, I'd like to book a pickup in Bhopal.", "Book a Pickup")),
        section(f'''                <article class="lp-article lp-guide">
{body_html}
                </article>'''),
        section(f'''                <h2>Let Cleanzit Handle It</h2>
                <div class="lp-chips">
{service_chips(ctx, g["services"])}
                </div>''', alt=True),
    ]
    ld_graph = [breadcrumb_ld(trail), {
        "@type": "Article", "@id": url + "#article", "headline": g["h1"], "description": g["description"],
        "datePublished": g["date"], "dateModified": g.get("updated", g["date"]), "inLanguage": "en-IN",
        "mainEntityOfPage": url, "author": ORG_REF, "publisher": ORG_REF,
        "image": f"{BASE}/assets/india_laundry_hero.png"}]
    if g.get("faqs"):
        parts.append(section(f"                <h2>Frequently Asked Questions</h2>\n{faq_block(g['faqs'])}"))
        ld_graph.append(faq_ld(g["faqs"], url))
    return page_shell(ctx, title=g["title"], description=g["description"], canonical=url, body="\n\n".join(parts),
                      ld=[{"@context": "https://schema.org", "@graph": ld_graph}], active="/guides/", og_type="article")


def build_guides_index(ctx):
    url = f"{BASE}/guides/"
    trail = [("Home", BASE + "/"), ("Guides", url)]
    cards = "\n".join(f'''                    <a class="lp-card" href="/guides/{g["slug"]}/">
                        <strong>{e(g["h1"])}</strong>
                        <span>{e(g["description"])}</span>
                    </a>''' for g in ctx["guides"])
    body = "\n\n".join([
        hero(trail, "Laundry &amp; Fabric Care <span>Guides</span>",
             "Practical advice from the Cleanzit team — care labels, stains, silk, woollens and more.",
             cta_pair("Hi Cleanzit, I'd like to book a pickup in Bhopal.", "Book a Pickup")),
        section(f'''                <div class="lp-cards">
{cards}
                </div>'''),
    ])
    ld = [{"@context": "https://schema.org", "@graph": [breadcrumb_ld(trail), {
        "@type": "ItemList", "name": "Cleanzit fabric care guides", "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "name": g["h1"], "url": f"{BASE}/guides/{g['slug']}/"}
            for i, g in enumerate(ctx["guides"])]}]}]
    return page_shell(ctx, title="Laundry & Fabric Care Guides | Cleanzit Bhopal",
                      description="Care labels, stain first aid, silk saree and lehenga care, and winter woollens — practical fabric care guides from Cleanzit, Bhopal.",
                      canonical=url, body=body, ld=ld, active="/guides/")


# ============================================================ Bhopal pages
def build_hub(ctx):
    P, B = ctx["prices"], ctx["bhopal"]
    f = P.facts
    url = f"{BASE}/bhopal/"
    trail = [("Home", BASE + "/"), ("Bhopal", url)]
    n_out, n_areas = len(B["outlets"]), len(B["areas"])
    qas = [
        ("Where are Cleanzit's laundry outlets in Bhopal?",
         f"Cleanzit has {n_out} outlets in Bhopal: " + "; ".join(f"{o['short']} — {full_address(o)}" for o in B["outlets"]) + "."),
        ("Do you offer free laundry pickup and delivery in Bhopal?",
         f"Yes. Pickup and delivery are free on orders above ₹{f['free_pickup_min']}. Book on WhatsApp at {PHONE_ORDERS_DISPLAY} and we'll collect from your door."),
        ("How much does laundry cost in Bhopal?",
         P.fill("Wash & Fold is {p:wash-fold:price} per kg and Wash & Steam Iron is {p:wash-iron:price} per kg. Shirt dry cleaning is {p:shirt:dry}. New customers get {fact:first_order_off}% off their first order.")),
        ("How long does laundry and dry cleaning take?",
         f"Standard delivery is within {f['delivery_days']} days for laundry, dry cleaning, woolens, household items and shoes."),
        ("Which areas of Bhopal does Cleanzit cover?",
         "Free doorstep pickup and delivery across Bhopal — " + "; ".join(
             z + ": " + ", ".join(a["name"] for a in B["areas"] if a["zone"] == z) for z in B["zones"]) + "."),
    ]
    outlets = "\n".join(outlet_card(o) for o in B["outlets"])
    lede = P.fill(f"{n_out} Cleanzit outlets and free doorstep pickup &amp; delivery on orders above ₹{{fact:free_pickup_min}}. "
                  "Laundry {p:wash-fold:price}/kg, shirt dry cleaning {p:shirt:dry}, delivered in {fact:delivery_days} days — and {fact:first_order_off}% off your first order.")
    body = "\n\n".join([
        hero(trail, "Laundry &amp; Dry Cleaning in <span>Bhopal</span>", lede,
             cta_pair("Hi Cleanzit, I'd like to book a laundry pickup in Bhopal.", "Book a Pickup")),
        section(f'''                <h2>Our Outlets in Bhopal</h2>
                <p class="lp-sub">Drop in at any outlet, or let us come to you — every outlet runs free pickup &amp; delivery.</p>
                <div class="lp-outlets">
{outlets}
                </div>''', alt=True, id_="outlets"),
        section(f'''                <h2>📍 Areas We Serve in Bhopal</h2>
                <p class="lp-sub">Free doorstep pickup &amp; delivery across {n_areas} neighbourhoods. Pick your area for local details and your closest outlet.</p>
{area_groups(ctx)}
                <p class="lp-sub" style="margin-top:1rem;">Don't see your area? <a href="{e(wa_link("Hi Cleanzit, do you pick up from my area in Bhopal?"))}" target="_blank" rel="noopener">Ask us on WhatsApp</a> — we'll confirm the same day.</p>''', id_="areas"),
        section(f'''                <h2>Our Services</h2>
                <div class="lp-chips">
{service_chips(ctx)}
                </div>''', alt=True),
        section(f'''                <h2>Popular Prices</h2>
                <p class="lp-sub">Transparent, itemised pricing. <a href="/pricing.html">See the full price list →</a></p>
{price_rows_table(ctx, B["headline_prices"], "Popular Cleanzit prices in Bhopal")}'''),
        section(f"                <h2>How It Works</h2>\n{steps_html(ctx)}", alt=True),
        section(f"                <h2>Frequently Asked Questions</h2>\n{faq_block(qas)}"),
    ])
    ld = [{"@context": "https://schema.org", "@graph": [
        breadcrumb_ld(trail), *[outlet_ld(o) for o in B["outlets"]],
        {"@type": "ItemList", "name": "Areas served in Bhopal", "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "name": f"Laundry in {a['name']}, Bhopal",
             "url": f"{BASE}/bhopal/{slugify(a['name'])}/"} for i, a in enumerate(B["areas"])]},
        faq_ld(qas, url)]}]
    return page_shell(ctx, title="Laundry & Dry Cleaning in Bhopal | Free Pickup | Cleanzit",
                      description=f"Cleanzit laundry & dry cleaning in Bhopal: {n_out} outlets, free pickup across {n_areas} areas. " + P.fill("Wash & fold {p:wash-fold:price}/kg, free pickup above ₹{fact:free_pickup_min}, {fact:first_order_off}% off first order."),
                      canonical=url, body=body, ld=ld, active="/bhopal/")


def build_area(ctx, area):
    P, B = ctx["prices"], ctx["bhopal"]
    f = P.facts
    name = area["name"]
    url = f"{BASE}/bhopal/{slugify(name)}/"
    trail = [("Home", BASE + "/"), ("Bhopal", BASE + "/bhopal/"), (name, url)]
    o = ctx["outlets_by_id"][area["outlet"]]
    others = [x for x in B["outlets"] if x["id"] != o["id"]]
    nearby = [a for a in B["areas"] if a["zone"] == area["zone"] and a["name"] != name]
    aka = f" (also known as {area['aka']})" if area.get("aka") else ""
    where = (f"Our {o['short']} outlet is right here in {name}" if o["locality"].lower() == name.lower()
             else f"Your closest outlet is Cleanzit {o['short']}")
    qas = [
        (f"Do you offer laundry pickup in {name}, Bhopal?",
         f"Yes. Cleanzit picks up and delivers across {name}{aka}, free on orders above ₹{f['free_pickup_min']}. Book on WhatsApp at {PHONE_ORDERS_DISPLAY} with your address and a preferred time."),
        (f"Which Cleanzit outlet is closest to {name}?",
         f"{where}, at {full_address(o)}. You can also drop off at any of our {len(B['outlets'])} Bhopal outlets."),
        (f"How much does dry cleaning cost in {name}?",
         P.fill("Prices are the same across Bhopal: shirt or trouser dry cleaning {p:shirt:dry}, 2-piece suit {p:suit-2:dry}, saree from {p:saree:dry}. Laundry is {p:wash-fold:price}/kg (wash & fold) or {p:wash-iron:price}/kg (wash & steam iron). New customers get {fact:first_order_off}% off the first order.")),
        (f"How long does delivery take in {name}?",
         f"Standard delivery in {name} is within {f['delivery_days']} days for laundry, dry cleaning, woolens, household items and shoes."),
    ]
    nearby_chips = "\n".join(f'                    <a href="/bhopal/{slugify(a["name"])}/">Laundry in {e(a["name"])}</a>' for a in nearby)
    lede = e(f"Free doorstep pickup & delivery in {name}{aka} on orders above ₹{f['free_pickup_min']}. {where} — ") + \
        P.fill("laundry {p:wash-fold:price}/kg, shirt dry cleaning {p:shirt:dry}, back to you in {fact:delivery_days} days. {fact:first_order_off}% off your first order.")
    body = "\n\n".join([
        hero(trail, f"Laundry &amp; Dry Cleaning in <span>{e(name)}</span>, Bhopal", lede,
             cta_pair(f"Hi Cleanzit, I'd like to book a laundry pickup in {name}, Bhopal.", f"Book a Pickup in {name}")),
        section(f'''                <h2>Your Closest Cleanzit Outlet</h2>
                <p class="lp-sub">Drop off in person, or book a pickup and we'll come to you in {e(name)}.</p>
                <div class="lp-outlets" style="max-width:520px;">
{outlet_card(o, closest=True)}
                </div>''', alt=True),
        section(f'''                <h2>Services in {e(name)}</h2>
                <p class="lp-sub">Everything below is available with doorstep pickup in {e(name)}.</p>
                <div class="lp-chips">
{service_chips(ctx)}
                </div>'''),
        section(f'''                <h2>Prices in {e(name)}</h2>
                <p class="lp-sub">Same transparent prices at every Cleanzit outlet. <a href="/pricing.html">Full price list →</a></p>
{price_rows_table(ctx, B["headline_prices"], f"Popular Cleanzit prices in {name}")}''', alt=True),
        section(f"                <h2>How Pickup Works in {e(name)}</h2>\n{steps_html(ctx)}"),
        section(f"                <h2>Frequently Asked Questions</h2>\n{faq_block(qas)}", alt=True),
        section(f'''                <h2>Nearby Areas</h2>
                <p class="lp-sub">Other areas in {e(area["zone"])} we pick up from.</p>
                <div class="lp-chips">
{nearby_chips}
                </div>
                <p class="lp-center"><a class="btn btn-outline" href="/bhopal/">All Bhopal areas &amp; outlets</a></p>'''),
        section(f'''                <h2>Other Cleanzit Outlets in Bhopal</h2>
                <div class="lp-outlets">
{chr(10).join(outlet_card(x) for x in others)}
                </div>''', alt=True),
    ])
    wf = P.cell("wash-fold:price")
    ld = [{"@context": "https://schema.org", "@graph": [
        breadcrumb_ld(trail),
        {"@type": "Service", "@id": url + "#service", "name": f"Laundry & dry cleaning in {name}, Bhopal",
         "serviceType": "Laundry, dry cleaning and steam ironing with free pickup and delivery",
         "areaServed": {"@type": "Place", "name": f"{name}, Bhopal, Madhya Pradesh"},
         "provider": outlet_ld(o), "offers": P.offer_ld(wf)},
        faq_ld(qas, url)]}]
    alias = f" ({area['aka']})" if area.get("aka") else ""
    return page_shell(ctx, title=f"Laundry & Dry Cleaning in {name}, Bhopal | Cleanzit",
                      description=clamp_desc(f"Laundry & dry cleaning in {name}{alias}, Bhopal.", f"Free pickup above ₹{f['free_pickup_min']},",
                                             P.fill("{fact:delivery_days}-day delivery, {fact:first_order_off}% off first order."), f"Nearest outlet: {o['short']}."),
                      canonical=url, body=body, ld=ld, active="/bhopal/")


# ============================================================ pricing.html regions
CAT_ICON = {"laundry": "⚡", "men": "🕒", "women": "🕒", "woolen": "❄️", "household": "🏠", "shoes": "👟", "bags": "👜"}
CAT_SERVICE = {"laundry": "laundry-service-bhopal", "men": "dry-cleaning-bhopal", "women": "saree-lehenga-dry-cleaning-bhopal",
               "woolen": "woolen-dry-cleaning-bhopal", "household": "blanket-quilt-cleaning-bhopal",
               "shoes": "shoe-cleaning-bhopal", "bags": "bag-cleaning-bhopal"}


def delivery_note(icon, text):
    return f'<div class="delivery-note">\n    <span>{icon}</span> {text}\n</div>'


def learn_more(ctx, slug):
    s = ctx["services_by_slug"][slug]
    return f'<p class="lp-learn"><a href="/services/{slug}/">More about {e(s["name"].lower())} in Bhopal →</a></p>'


def price_table(ctx, cat):
    P = ctx["prices"]
    cols = list(cat["columns"].items())
    head = "".join(f"<th>{e(label)}</th>" for _, label in cols)
    rows = []
    for it in cat["items"]:
        cells = []
        for key, _ in cols:
            v = it.get(key, "")
            cells.append(f'<td class="price-val">{P.rupees(v) + (" / " + it["unit"] if it.get("unit") else "") if v else "—"}</td>')
        rows.append(f'            <tr>\n                <td>{e(it["name"])}</td>\n                ' + "\n                ".join(cells) + "\n            </tr>")
    return f'''<div class="pricing-table-container">
    <table class="pricing-table">
        <thead>
            <tr><th>Item</th>{head}</tr>
        </thead>
        <tbody>
{chr(10).join(rows)}
        </tbody>
    </table>
</div>'''


def std_note(ctx, cat):
    return delivery_note(CAT_ICON[cat["id"]], f'Standard delivery within {ctx["prices"].facts["delivery_days"]} days · a “+” after a price means “starting from”')


def panel_laundry(ctx):
    P = ctx["prices"]
    cat = next(c for c in P.data["categories"] if c["id"] == "laundry")
    cards = []
    for i, it in enumerate(cat["items"]):
        dark = i == 1
        box = ("background: linear-gradient(135deg, var(--color-primary) 0%, var(--color-primary-light) 100%); color: #fff;"
               if dark else "background: #fff; border: 1px solid rgba(0,0,0,0.05);")
        h3c = "var(--color-secondary)" if dark else "var(--color-primary)"
        pc = "#fff" if dark else "var(--color-primary)"
        cards.append(f'''    <div style="{box} padding: 2rem; border-radius: 16px; text-align: center;">
        <div style="font-size: 3rem; margin-bottom: 1rem;">{it["icon"]}</div>
        <h3 style="color: {h3c}; margin-bottom: 0.5rem;">{e(it["name"])}</h3>
        <div style="font-size: 2.5rem; font-weight: 800; color: {pc}; margin: 0.5rem 0;">{P.rupees(it["price"])}<span style="font-size: 1rem; font-weight: 500; opacity: 0.8;">/{it["unit"]}</span></div>
        <p style="opacity: 0.85;">{e(it["note"])}</p>
    </div>''')
    extra = ", ".join(P.data["additional_services"])
    return "\n".join([std_note(ctx, cat),
                      '<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 1.5rem;">',
                      "\n".join(cards), "</div>",
                      f'<p class="lp-learn">Additional services available: {e(extra)}. Approx 5 everyday garments per kg.</p>',
                      learn_more(ctx, "laundry-service-bhopal")])


def panel_table(ctx, cid):
    cat = next(c for c in ctx["prices"].data["categories"] if c["id"] == cid)
    extra = learn_more(ctx, CAT_SERVICE[cid])
    if cid == "men":
        extra += "\n" + learn_more(ctx, "steam-ironing-bhopal")
    return "\n".join([std_note(ctx, cat), price_table(ctx, cat), extra])


def panel_shoesbags(ctx):
    cats = {c["id"]: c for c in ctx["prices"].data["categories"]}
    return "\n".join([std_note(ctx, cats["shoes"]),
                      '<h3 style="color: var(--color-primary); margin: 1.5rem 0 1rem; font-size: 1.1rem;">Shoe Cleaning</h3>',
                      price_table(ctx, cats["shoes"]), learn_more(ctx, "shoe-cleaning-bhopal"),
                      '<h3 style="color: var(--color-primary); margin: 2rem 0 1rem; font-size: 1.1rem;">Bag Cleaning</h3>',
                      price_table(ctx, cats["bags"]), learn_more(ctx, "bag-cleaning-bhopal")])


def panel_home(ctx):
    P = ctx["prices"]
    hs = P.data["home_services"]
    note = (f'{e(hs["label"])} — {e(hs["headline"])}' if P.offer_on else "Professional cleaning at your home in Bhopal")
    home_pages = {"home-curtain": "curtain-cleaning-bhopal", "home-carpet": "carpet-cleaning-bhopal", "home-sofa": "sofa-cleaning-bhopal",
                  "home-mattress": "mattress-cleaning-bhopal", "home-floor": "home-deep-cleaning-bhopal", "home-kitchen": "home-deep-cleaning-bhopal"}
    cards = []
    for h in hs["items"]:
        unit = f"/{h['unit']}" if h["unit"] else ""
        if P.offer_on and h["was"] != h["now"]:
            price = (f'<span style="text-decoration: line-through; color: #94a3b8;">{P.rupees(h["was"], False)}{unit}</span>\n'
                     f'            <span class="lp-offer-price">{P.rupees(h["now"], False)}{unit}</span>')
        else:
            price = f'<span class="lp-offer-price">{P.rupees(h["now"], False)}{unit}</span>'
        cards.append(f'''    <a href="/services/{home_pages[h["id"]]}/" class="lp-home-card">
        <div style="font-size: 2.5rem; margin-bottom: 0.75rem;">{h["icon"]}</div>
        <h3>{e(h["name"])}</h3>
        <p>Starting at</p>
        <div>{price}</div>
    </a>''')
    return "\n".join([delivery_note("🪔" if P.offer_on else "🏡", note),
                      '<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 1.25rem;">',
                      "\n".join(cards), "</div>",
                      '<p class="lp-learn">Our home-services team comes to your home in Bhopal. Ask our staff which services are part of the current offer.</p>',
                      learn_more(ctx, "home-deep-cleaning-bhopal")])


def panel_membership(ctx):
    P = ctx["prices"]
    cards = "\n".join(f'''    <div style="background: #fff; padding: 2rem; border-radius: 16px; text-align: center; border: 2px solid {m["border"]};">
        <div style="font-size: 2.5rem; margin-bottom: 0.5rem;">{m["icon"]}</div>
        <h3 style="color: var(--color-primary); letter-spacing: 0.5px;">{e(m["name"].upper())}</h3>
        <div style="font-size: 2rem; font-weight: 800; color: var(--color-primary); margin: 0.75rem 0 0.25rem;">{P.rupees(m["topup"])}</div>
        <p style="color: var(--color-text-light); font-size: 0.8rem; text-transform: uppercase; letter-spacing: 1px;">Top-up</p>
        <div style="font-size: 1.5rem; font-weight: 800; color: #D0103A; margin: 0.75rem 0;">{m["discount"]}% OFF</div>
        <p style="color: var(--color-text-light); font-size: 0.9rem;">{e(m["blurb"])}</p>
    </div>''' for m in P.data["membership"])
    return "\n".join([delivery_note("🎖️", "Top up your Cleanzit account and get a member discount on select services"),
                      '<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 1.5rem; max-width: 780px; margin: 0 auto;">',
                      cards, "</div>", f'<p class="lp-learn">{e(P.data["membership_note"])}</p>'])


def pricing_ld(ctx):
    P = ctx["prices"]
    catalogs = []
    for cat in P.data["categories"]:
        offers = [P.offer_ld(P.cell(f"{it['id']}:{col}")) for it in cat["items"] for col in cat["columns"] if it.get(col)]
        catalogs.append({"@type": "OfferCatalog", "name": cat["name"], "itemListElement": offers})
    catalogs.append({"@type": "OfferCatalog", "name": "Home cleaning services",
                     "itemListElement": [P.offer_ld(P.cell("home:" + h["id"])) for h in P.data["home_services"]["items"]]})
    catalogs.append({"@type": "OfferCatalog", "name": "Membership plans", "itemListElement": [
        {"@type": "Offer", "name": f"{m['name']} top-up", "priceCurrency": "INR", "price": m["topup"], "description": m["blurb"]}
        for m in P.data["membership"]]})
    return {"@context": "https://schema.org", "@graph": [{
        "@type": "Service", "@id": f"{BASE}/pricing.html#pricelist", "name": "Cleanzit price list — Bhopal",
        "serviceType": "Laundry, dry cleaning, steam ironing and home cleaning", "provider": ORG_REF,
        "areaServed": {"@type": "City", "name": "Bhopal"}, "hasOfferCatalog": catalogs}]}


def calculator(ctx):
    P = ctx["prices"]
    f = P.facts
    rows = []
    for ref in P.data["calculator"]:
        c = P.cell(ref)
        it = c["item"]
        cat = P.cat_of[it["id"]]
        col = ref.split(":")[1]
        kind = cat["columns"][col] if len(cat["columns"]) > 1 else ""
        sub = (f"{kind} · " if kind else "") + c["display"]
        rows.append(f'''    <div class="calc-row" data-label="{e(c["label"])}" data-price="{c["num"]}" data-from="{1 if c["plus"] else 0}" data-unit="{e(c["unit"])}">
        <div class="calc-name"><strong>{e(it["name"])}</strong><span>{e(sub)}</span></div>
        <div class="calc-qty">
            <button type="button" data-step="-1" aria-label="Remove one: {e(c["label"])}">−</button>
            <output>0</output>
            <button type="button" data-step="1" aria-label="Add one: {e(c["label"])}">+</button>
        </div>
    </div>''')
    return f'''<h2>Estimate Your Bill</h2>
<p class="lp-sub">Add your items to see an instant estimate, then send the list to us on WhatsApp to book a pickup.</p>
<div class="calc" data-free-min="{f["free_pickup_min"]}" data-first-off="{f["first_order_off"]}" data-wa="{PHONE_ORDERS}">
<div class="calc-items">
{chr(10).join(rows)}
</div>
<aside class="calc-summary">
    <h3>Your Estimate</h3>
    <dl aria-live="polite">
        <div><dt>Items</dt><dd data-out="count">0</dd></div>
        <div><dt>Estimated total</dt><dd data-out="total">₹0</dd></div>
        <div><dt>Pickup &amp; delivery</dt><dd data-out="pickup">Free above ₹{f["free_pickup_min"]}</dd></div>
        <div><dt>First order ({f["first_order_off"]}% off)</dt><dd data-out="first">₹0</dd></div>
    </dl>
    <p class="calc-note" data-out="note">Prices marked “+” are starting prices; the final bill depends on fabric and condition.</p>
    <a class="btn calc-wa" data-out="wa" href="{e(wa_link("Hi Cleanzit, I'd like to book a pickup."))}" target="_blank" rel="noopener">💬 Book on WhatsApp</a>
</aside>
</div>
<noscript><p class="lp-sub">Turn on JavaScript to use the estimator — or see the full price list above.</p></noscript>
<script src="/js/estimator.js" defer></script>'''


# ============================================================ other hand-written page regions
def service_grid(ctx, slugs, detailed):
    cards = []
    for sl in slugs:
        s = ctx["services_by_slug"][sl]
        st = service_start(ctx, s)
        price = f"Starting {st[0]}" if st else "Ask for a quote"
        blurb = f"\n        <p>{e(ctx['prices'].fill(s['short']))}</p>" if detailed else ""
        more = '\n        <span class="lp-more">Learn more →</span>' if detailed else ""
        cards.append(f'''    <a class="lp-service{' is-detailed' if detailed else ''}" href="/services/{sl}/">
        <span class="lp-service-icon" aria-hidden="true">{s["icon"]}</span>
        <h3>{e(s["name"])}</h3>{blurb}
        <strong>{e(price)}</strong>{more}
    </a>''')
    return '<div class="lp-service-grid">\n' + "\n".join(cards) + "\n</div>"


def indent_block(text, indent):
    return "\n".join((indent + l) if l.strip() else l for l in text.splitlines())


def replace_region(path, name, make):
    """Fill <!-- BEGIN:gen:NAME ... --> ... <!-- END:gen:NAME --> with make(indent)."""
    full = os.path.join(ROOT, path)
    s = open(full, encoding="utf-8").read()
    # The name must end at whitespace or "-->", so gen:outlets never matches gen:outlets-ld.
    pat = re.compile(r"^([ \t]*)(<!-- BEGIN:gen:%s(?:\s[^>]*)?-->)(.*?)(^[ \t]*<!-- END:gen:%s -->)" % (re.escape(name), re.escape(name)), re.S | re.M)
    found = pat.findall(s)
    if len(found) != 1:
        fail(f"{path}: expected exactly one gen:{name} region, found {len(found)}")
    s = pat.sub(lambda m: m.group(1) + m.group(2) + "\n" + make(m.group(1)) + "\n" + m.group(4), s, count=1)
    open(full, "w", encoding="utf-8").write(s)


STATIC_ACTIVE = {"index.html": "", "about.html": "/about.html", "services.html": "/services.html", "pricing.html": "/pricing.html",
                 "stores.html": "/stores.html", "contact.html": "/contact.html"}


def fill_static_pages(ctx):
    B = ctx["bhopal"]
    outlets_ld = {"@context": "https://schema.org", "@graph": [outlet_ld(o) for o in B["outlets"]]}
    for p in STATIC_PAGES:
        replace_region(p, "nav", lambda ind, p=p: nav_items(STATIC_ACTIVE[p], ind))
        replace_region(p, "footer", lambda ind: footer_cols(ctx, ind))
    replace_region("stores.html", "outlets", lambda ind: indent_block("\n".join(outlet_card(o, heading="h2") for o in B["outlets"]), ind))
    replace_region("stores.html", "outlets-ld", lambda ind: ld_script(outlets_ld, ind))
    replace_region("index.html", "outlets-ld", lambda ind: ld_script(outlets_ld, ind))
    replace_region("index.html", "areas", lambda ind: indent_block(area_groups(ctx, per_zone=6), ind))
    replace_region("index.html", "home-services", lambda ind: indent_block(service_grid(ctx, ctx["services"]["home_page"], False), ind))
    replace_region("services.html", "service-cards", lambda ind: indent_block(service_grid(ctx, [s["slug"] for s in ctx["services"]["services"]], True), ind))
    panels = {"laundry": panel_laundry, "men": lambda c: panel_table(c, "men"), "women": lambda c: panel_table(c, "women"),
              "woolen": lambda c: panel_table(c, "woolen"), "household": lambda c: panel_table(c, "household"),
              "shoesbags": panel_shoesbags, "homeservices": panel_home, "membership": panel_membership}
    for pid, fn in panels.items():
        replace_region("pricing.html", f"panel-{pid}", lambda ind, fn=fn: indent_block(fn(ctx), ind))
    replace_region("pricing.html", "pricing-ld", lambda ind: ld_script(pricing_ld(ctx), ind))
    replace_region("pricing.html", "calculator", lambda ind: indent_block(calculator(ctx), ind))


def check_handwritten_prices(ctx):
    """Hand-written copy sometimes quotes a per-kg price ("starting at ₹60/kg").
    Fail the build if any such figure is not a real per-kg price, so prose can't
    drift from data/prices.json unnoticed."""
    per_kg = {str(ctx["prices"].num(it["price"])) for it in next(c for c in ctx["prices"].data["categories"] if c["id"] == "laundry")["items"]}
    for p in STATIC_PAGES:
        text = open(os.path.join(ROOT, p), encoding="utf-8").read()
        for n in re.findall(r"₹\s?([\d,]+)\s?/\s?kg", text):
            if n.replace(",", "") not in per_kg:
                fail(f"{p} quotes ₹{n}/kg, which is not a per-kg price in data/prices.json (valid: {sorted(per_kg)})")


def fill_llms(ctx):
    P, B = ctx["prices"], ctx["bhopal"]

    def areas(_):
        lines = ["Free pickup and delivery across these Bhopal areas (each has its own page",
                 f"at {BASE}/bhopal/<area>/):", ""]
        for z in B["zones"]:
            lines.append(f"- {z}: " + ", ".join(a["name"] + (f" ({a['aka']})" if a.get("aka") else "")
                                               for a in B["areas"] if a["zone"] == z))
        return "\n".join(lines)

    def prices(_):
        out = [f"All prices in Indian rupees. A '+' means 'starting from'. Standard delivery within {P.facts['delivery_days']} days.", ""]
        for cat in P.data["categories"]:
            out.append(f"## {cat['name']}")
            out.append("")
            for it in cat["items"]:
                vals = []
                for col, label in cat["columns"].items():
                    if it.get(col):
                        v = P.rupees(it[col]).replace("₹", "Rs ") + (f"/{it['unit']}" if it.get("unit") else "")
                        vals.append(v if len(cat["columns"]) == 1 else f"{label.lower()} {v}")
                out.append(f"- {it['name']} — " + ", ".join(vals))
            out.append("")
        hs = P.data["home_services"]
        out.append("## Home cleaning services" + (f" ({hs['label']}: {hs['headline']})" if P.offer_on else ""))
        out.append("")
        for h in hs["items"]:
            unit = f"/{h['unit']}" if h["unit"] else ""
            was = f" (regular Rs {int(h['was']):,}{unit})" if P.offer_on and h["was"] != h["now"] else ""
            out.append(f"- {h['name']} at home — from Rs {int(h['now']):,}{unit}{was}")
        out += ["", "## Membership", ""]
        out += [f"- {m['name']} — Rs {int(m['topup']):,} top-up, {m['discount']}% discount on select services" for m in P.data["membership"]]
        out += ["", "Additional services: " + ", ".join(P.data["additional_services"]) + "."]
        return "\n".join(out)

    def pages(_):
        out = ["Services:"]
        out += [f"- {s['h1']}: {BASE}/services/{s['slug']}/" for s in ctx["services"]["services"]]
        out += ["", "Guides:"]
        out += [f"- {g['h1']}: {BASE}/guides/{g['slug']}/" for g in ctx["guides"]]
        out += ["", f"Full price list: {BASE}/pricing.html", f"Bhopal outlets and areas: {BASE}/bhopal/"]
        return "\n".join(out)

    replace_region("llms.txt", "areas", areas)
    replace_region("llms.txt", "prices", prices)
    replace_region("llms.txt", "pages", pages)


def write_sitemap(ctx, urls):
    today = datetime.date.today().isoformat()
    items = "\n".join(f"  <url>\n    <loc>{u}</loc>\n    <lastmod>{today}</lastmod>\n    <priority>{p}</priority>\n  </url>" for u, p in urls)
    write("sitemap.xml", '<?xml version="1.0" encoding="UTF-8"?>\n<!-- Generated by tools/build_site.py -->\n'
          f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{items}\n</urlset>\n')


def prune(folder, keep):
    removed = 0
    d = os.path.join(ROOT, folder)
    for entry in os.listdir(d):
        p = os.path.join(d, entry)
        if os.path.isdir(p) and entry not in keep:
            shutil.rmtree(p)
            removed += 1
    return removed


# ============================================================ main
def main():
    prices = Prices(load("data/prices.json"))
    services = load("data/services.json")
    bhopal = load("data/bhopal.json")
    guides = load_guides(prices)
    ctx = {"prices": prices, "services": services, "bhopal": bhopal, "guides": guides,
           "services_by_slug": {s["slug"]: s for s in services["services"]},
           "guides_by_slug": {g["slug"]: g for g in guides},
           "outlets_by_id": {o["id"]: o for o in bhopal["outlets"]}}

    # ---- validate cross-references before writing anything
    svc = ctx["services_by_slug"]
    if len(svc) != len(services["services"]):
        fail("duplicate service slug")
    for s in services["services"]:
        for r in s["related"] + services["home_page"] + services["footer"]:
            if r not in svc:
                fail(f"unknown service slug {r!r}")
        if s.get("start"):
            prices.cell(s["start"])
        if s.get("guide") and s["guide"] not in ctx["guides_by_slug"]:
            fail(f"service {s['slug']} links unknown guide {s['guide']!r}")
        for r in s["prices"]:
            prices.cell(r)
        for h in s.get("home", []):
            prices.cell("home:" + h)
    for g in guides:
        for r in g["services"]:
            if r not in svc:
                fail(f"guide {g['slug']} links unknown service {r!r}")
    for r in bhopal["headline_prices"]:
        prices.cell(r)
    for ref in prices.data["calculator"]:
        prices.cell(ref)
    names = {a["name"] for a in bhopal["areas"]}
    if len(names) != len(bhopal["areas"]):
        fail("duplicate area name")
    for a in bhopal["areas"]:
        if a["outlet"] not in ctx["outlets_by_id"]:
            fail(f"area {a['name']!r}: unknown outlet {a['outlet']!r}")
        if a["zone"] not in bhopal["zones"]:
            fail(f"area {a['name']!r}: unknown zone {a['zone']!r}")
    for n in bhopal["footer_areas"]:
        if n not in names:
            fail(f"footer_areas: {n!r} is not an area")
    slugs = [slugify(a["name"]) for a in bhopal["areas"]]
    if len(set(slugs)) != len(slugs):
        fail("two areas produce the same URL slug")

    # ---- pages
    urls = [(f"{BASE}/", "1.0"), (f"{BASE}/pricing.html", "0.9"), (f"{BASE}/services.html", "0.9"),
            (f"{BASE}/stores.html", "0.7"), (f"{BASE}/about.html", "0.5"), (f"{BASE}/contact.html", "0.6")]
    for s in services["services"]:
        write(f"services/{s['slug']}/index.html", build_service(ctx, s))
        urls.append((f"{BASE}/services/{s['slug']}/", "0.8"))
    write("services/index.html", build_services_redirect())
    write("guides/index.html", build_guides_index(ctx))
    urls.append((f"{BASE}/guides/", "0.6"))
    for g in guides:
        write(f"guides/{g['slug']}/index.html", build_guide(ctx, g))
        urls.append((f"{BASE}/guides/{g['slug']}/", "0.6"))
    write("bhopal/index.html", build_hub(ctx))
    urls.append((f"{BASE}/bhopal/", "0.9"))
    for a in bhopal["areas"]:
        write(f"bhopal/{slugify(a['name'])}/index.html", build_area(ctx, a))
        urls.append((f"{BASE}/bhopal/{slugify(a['name'])}/", "0.7"))
    removed = (prune("services", {s["slug"] for s in services["services"]}) + prune("guides", {g["slug"] for g in guides})
               + prune("bhopal", set(slugs)))

    check_handwritten_prices(ctx)
    fill_static_pages(ctx)
    fill_llms(ctx)
    write_sitemap(ctx, urls)
    print(f"built {len(services['services'])} service pages, {len(guides)} guides, Bhopal hub + {len(bhopal['areas'])} areas "
          f"({removed} stale removed); refreshed 6 hand-written pages + llms.txt; sitemap.xml has {len(urls)} URLs")


if __name__ == "__main__":
    main()
