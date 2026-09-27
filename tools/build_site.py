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
the hand-written pages (nav + footer on all of them; price panels, structured data
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
STATIC_PAGES = ["index.html", "about.html", "services.html", "pricing.html", "stores.html", "contact.html", "franchise.html"]
NAV = [("About", "/about.html"), ("Services", "/services.html"), ("Pricing", "/pricing.html"),
       ("Areas", "/bhopal/"), ("Guides", "/guides/"), ("Stores", "/stores.html"), ("Contact", "/contact.html")]
ORG_REF = {"@type": "Organization", "@id": f"{BASE}/#organization", "name": "Cleanzit", "url": f"{BASE}/"}

e = html.escape

# UI strings for shared components. Page copy lives in data/ and content/.
T = {
    "en": {
        "nav": [("Services", "/services.html"), ("Pricing", "/pricing.html"), ("Stores", "/stores.html"), ("Contact", "/contact.html")],
        "lang_link": ("हिंदी", "/hi/", "hi"), "book_btn": "Book Pickup", "book_href": "/book/",
        "fine": "Free pickup & delivery on orders above ₹{min} · {off}% off your first order · Open 7 days",
        "status": "Already booked? Ask for your order status on WhatsApp", "status_msg": "Hi Cleanzit, I'd like to know the status of my order.",
        "intro": "Hi Cleanzit, I'd like to book a pickup.",
        "bar_call": "Call", "bar_wa": "WhatsApp", "bar_book": "Book Pickup",
    },
    "hi": {
        "nav": [("सेवाएं", "/hi/#services"), ("कीमतें", "/pricing.html"), ("स्टोर", "/stores.html"), ("संपर्क", "/contact.html")],
        "lang_link": ("English", "/", "en"), "book_btn": "पिकअप बुक करें", "book_href": "/hi/#book",
        "fine": "₹{min} से ज़्यादा के ऑर्डर पर फ्री पिकअप और डिलीवरी · पहले ऑर्डर पर {off}% छूट · हफ्ते के सातों दिन खुला",
        "status": "पहले से बुक किया है? अपने ऑर्डर का स्टेटस WhatsApp पर पूछें", "status_msg": "नमस्ते Cleanzit, मुझे अपने ऑर्डर का स्टेटस जानना है।",
        "intro": "नमस्ते Cleanzit, मुझे पिकअप बुक करना है।",
        "bar_call": "कॉल", "bar_wa": "WhatsApp", "bar_book": "पिकअप बुक करें",
    },
}


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
            return {"label": f"{h['name']} (at home)", "short_label": h["name"], "value": h["now"], "col_label": "",
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
        return {"label": label, "short_label": it["name"], "value": v, "col_label": cat["columns"][col] if multi else "",
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


# ============================================================ Hindi helpers
def hi_label(ctx, c):
    hi = ctx["hi"]
    name = hi["item_names"].get(c["item"]["id"], c["short_label"])
    if c["kind"] == "home":
        return f"{name} (घर पर)"
    return name + (f" — {hi['column_names'].get(c['col_label'], c['col_label'])}" if c["col_label"] else "")


def hi_display(ctx, text):
    for en, hn in ctx["hi"]["unit_names"].items():
        text = text.replace(f"/ {en}", f"/ {hn}").replace(f"/{en}", f"/{hn}")
    return text


def cell_label(ctx, c, lang):
    return hi_label(ctx, c) if lang == "hi" else c["label"]


def cell_display(ctx, c, lang):
    return hi_display(ctx, c["display"]) if lang == "hi" else c["display"]


def hi_service_href(ctx, slug):
    """Hindi page if one exists, else the English one."""
    return f"/hi/services/{slug}/" if slug in ctx["hi_services"] else f"/services/{slug}/"


# ============================================================ shared fragments
def nav_items(active, indent, lang="en", alt_href=None):
    t = T[lang]
    li = []
    for name, href in t["nav"]:
        cls = ' class="active"' if href == active else ""
        li.append(f'{indent}<li><a href="{href}"{cls}>{name}</a></li>')
    label, href, code = t["lang_link"]
    li.append(f'{indent}<li><a href="{alt_href or href}" class="nav-lang" lang="{code}" hreflang="{code}">{label}</a></li>')
    li.append(f'{indent}<li><a href="{t["book_href"]}" class="btn nav-cta">{t["book_btn"]}</a></li>')
    return "\n".join(li)


def mobile_bar(lang="en"):
    t = T[lang]
    return f'''<div class="mobile-bar" role="navigation" aria-label="Quick actions">
    <a href="tel:+{PHONE_ORDERS}">📞 {t["bar_call"]}</a>
    <a href="https://wa.me/{PHONE_ORDERS}?text={urllib.parse.quote(t["intro"])}" target="_blank" rel="noopener">💬 {t["bar_wa"]}</a>
    <a href="{t["book_href"]}" class="mobile-bar-book">{t["bar_book"]}</a>
</div>'''


QB = {
    "en": {"step1": "What are you sending?", "tap_all": "tap all that apply", "step2": "Where should we pick up?", "optional": "optional",
           "area_ph": "Your area, e.g. Kolar Road", "send": "Send on WhatsApp",
           "fine": "We reply on WhatsApp to fix a pickup time · No app, no sign-up · Free pickup above ₹{min} · {off}% off your first order",
           "intro": "Hi Cleanzit! I'd like to book a pickup.", "for": "For", "area": "Area",
           "bag": "My bag", "status": "Already booked? Ask for your order status on WhatsApp",
           "status_msg": "Hi Cleanzit, I'd like to know the status of my order."},
    "hi": {"step1": "क्या भेजना है?", "tap_all": "जितने चाहें चुनें", "step2": "पिकअप कहां से करें?", "optional": "वैकल्पिक",
           "area_ph": "आपका इलाका, जैसे कोलार रोड", "send": "WhatsApp पर भेजें",
           "fine": "हम WhatsApp पर पिकअप का समय तय करेंगे · कोई ऐप या साइन-अप नहीं · ₹{min} से ज़्यादा पर फ्री पिकअप · पहले ऑर्डर पर {off}% छूट",
           "intro": "नमस्ते Cleanzit! मुझे पिकअप बुक करना है।", "for": "सेवा", "area": "इलाका",
           "bag": "मेरे कपड़े", "status": "पहले से बुक किया है? अपने ऑर्डर का स्टेटस WhatsApp पर पूछें",
           "status_msg": "नमस्ते Cleanzit, मुझे अपने ऑर्डर का स्टेटस जानना है।"},
}

# Line icons (48×48, stroke = currentColor) for the booking tiles and for
# service cards without a photo. booking_groups in data/services.json name
# them by key; SERVICE_GLYPH maps each service to one.
GLYPHS = {
    "shirt": '<path d="M17 7 8 11l3 8 4-2v24h18V17l4 2 3-8-9-4c-1 3-3.5 5-7 5s-6-2-7-5Z"/>',
    "hanger": '<path d="M20 10a4 4 0 1 1 5.5 3.7c-1 .4-1.5 1.2-1.5 2.3v2"/><path d="M24 18 6.8 31.4A2 2 0 0 0 8 35h32a2 2 0 0 0 1.2-3.6Z"/>',
    "shoe": '<path d="M5 36V23c0-2.5 2.5-3.5 4-2l3 2.5c2 1.5 4.5 1 5.5-1l1.5-3c.8-1.4 2.2-1.6 3.2-.4l3.3 4.4c3 3.5 7 5.5 12 6.5 3 .6 5.5 2.8 5.5 6Z"/><path d="M5 36h38v3H5z"/><path d="m19 22 3 2.5M22 18.5l3 2.5"/>',
    "home": '<path d="M7 22 24 8l17 14"/><path d="M11 19v20h26V19"/><path d="M20.5 39V29h7v10"/>',
    "iron": '<path d="M7 34h31a3 3 0 0 0 3-3c0-8.3-6.7-15-15-15H15"/><path d="M7 34c0-8 5-14 12-15"/><path d="M17 16c0-4 2.5-6 6-6h9"/><path d="M13 40h24"/>',
    "bag": '<path d="M9 18h30l-3 22H12Z"/><path d="M18 18v-3a6 6 0 0 1 12 0v3"/>',
    "lehenga": '<path d="M18 7h12l2 10H16Z"/><path d="M16 17 8 41h32l-8-24"/><path d="M9.3 37h29.4"/><path d="M24 17v24"/>',
    "sweater": '<path d="M17 8 8 13l2 12 4-2v17h20V23l4 2 2-12-9-5c-1 3-3.5 5-7 5s-6-2-7-5Z"/><path d="M14 35h20M10.5 21.5l3.5-1.5M37.5 21.5 34 20"/>',
    "blanket": '<rect x="9" y="11" width="30" height="8" rx="4"/><rect x="6" y="21" width="36" height="8" rx="4"/><rect x="9" y="31" width="30" height="8" rx="4"/>',
    "curtain": '<path d="M5 8h38"/><path d="M9 8c0 12 5 22 2 32h9c-2-12 0-24 0-32M39 8c0 12-5 22-2 32h-9c2-12 0-24 0-32"/>',
    "carpet": '<rect x="9" y="12" width="30" height="24" rx="1"/><path d="M12 12V8M17 12V8M22 12V8M27 12V8M32 12V8M37 12V8M12 40v-4M17 40v-4M22 40v-4M27 40v-4M32 40v-4M37 40v-4"/><path d="m24 17 7 7-7 7-7-7Z"/>',
    "sofa": '<path d="M10 22v-6a4 4 0 0 1 4-4h20a4 4 0 0 1 4 4v6"/><path d="M6 24a3 3 0 0 1 6 0v4h24v-4a3 3 0 0 1 6 0v10H6Z"/><path d="M10 34v4M38 34v4"/>',
    "mattress": '<rect x="5" y="19" width="38" height="15" rx="3"/><path d="M15 19v15M24 19v15M33 19v15M8 38h32"/>',
    "drop": '<path d="M24 7s-12 13.5-12 22a12 12 0 0 0 24 0C36 20.5 24 7 24 7Z"/><path d="M18 30a6 6 0 0 0 6 6"/>',
}
SERVICE_GLYPH = {
    "laundry-service-bhopal": "shirt", "dry-cleaning-bhopal": "hanger", "steam-ironing-bhopal": "iron",
    "shoe-cleaning-bhopal": "shoe", "bag-cleaning-bhopal": "bag", "saree-lehenga-dry-cleaning-bhopal": "lehenga",
    "woolen-dry-cleaning-bhopal": "sweater", "blanket-quilt-cleaning-bhopal": "blanket", "curtain-cleaning-bhopal": "curtain",
    "carpet-cleaning-bhopal": "carpet", "sofa-cleaning-bhopal": "sofa", "mattress-cleaning-bhopal": "mattress",
    "home-deep-cleaning-bhopal": "home", "stain-removal-bhopal": "drop",
}


def glyph(key, cls="glyph"):
    return (f'<svg class="{cls}" viewBox="0 0 48 48" aria-hidden="true" fill="none" stroke="currentColor" '
            f'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">{GLYPHS[key]}</svg>')


def check_booking_groups(ctx):
    """Every service sits in exactly one booking tile; every tile has Hindi text and a known icon."""
    slugs = [x["slug"] for x in ctx["services"]["services"]]
    seen = [sl for g in ctx["services"]["booking_groups"] for sl in g["services"]]
    for sl in slugs:
        if seen.count(sl) != 1:
            fail(f"data/services.json booking_groups: '{sl}' must be in exactly one group (found {seen.count(sl)})")
        if sl not in SERVICE_GLYPH:
            fail(f"tools/build_site.py SERVICE_GLYPH: no icon for '{sl}'")
    for sl in seen:
        if sl not in slugs:
            fail(f"data/services.json booking_groups: unknown service '{sl}'")
    for g in ctx["services"]["booking_groups"]:
        if g["id"] not in ctx["hi"]["booking_groups"]:
            fail(f"data/hi.json booking_groups: missing Hindi text for '{g['id']}'")
        if g["icon"] not in GLYPHS:
            fail(f"data/services.json booking_groups: unknown icon '{g['icon']}'")


def quick_book(ctx, lang="en"):
    """Two-step booking: tick what you're sending (any of the booking_groups
    tiles, optional), type an area (optional), send on WhatsApp. Name and
    number come from WhatsApp itself, so we don't ask for them. js/booking.js
    builds the message and pre-selects ?service=<slug>&area=<slug>&items=<bag>."""
    q = QB[lang]
    P, B = ctx["prices"], ctx["bhopal"]
    hi = ctx["hi"]
    tiles = []
    for g in ctx["services"]["booking_groups"]:
        text = hi["booking_groups"][g["id"]] if lang == "hi" else g
        tiles.append(f'''            <label class="qb-opt">
                <input type="checkbox" name="need" value="{e(text["name"])}" data-services="{" ".join(g["services"])}">
                <span class="qb-tick" aria-hidden="true"></span>
                {glyph(g["icon"], "qb-ico")}
                <strong>{e(text["name"])}</strong>
                <small>{e(text["hint"])}</small>
            </label>''')
    names = {sl: (hi["service_names"][sl] if lang == "hi" else ctx["services_by_slug"][sl]["name"])
             for g in ctx["services"]["booking_groups"] for sl in g["services"]}
    areas = "\n".join(f'        <option value="{e(hi["area_names"][a["name"]] if lang == "hi" else a["name"])}" data-slug="{slugify(a["name"])}"></option>' for a in B["areas"])
    fine = q["fine"].format(min=P.facts["free_pickup_min"], off=P.facts["first_order_off"])
    dl = "qb-areas-" + lang
    return f'''<form class="qb" id="book" novalidate data-wa="{PHONE_ORDERS}" data-intro="{e(q["intro"])}" data-for="{e(q["for"])}"
      data-area="{e(q["area"])}" data-bag="{e(q["bag"])}" data-names="{e(json.dumps(names, ensure_ascii=False))}">
    <fieldset class="qb-need">
        <legend class="qb-step"><span class="qb-num">1</span><span class="qb-h">{e(q["step1"])} <small>({e(q["tap_all"])})</small></span></legend>
        <div class="qb-opts">
{chr(10).join(tiles)}
        </div>
    </fieldset>
    <div class="qb-step"><span class="qb-num">2</span><h2 class="qb-h">{e(q["step2"])} <small>({e(q["optional"])})</small></h2></div>
    <div class="qb-row">
        <input name="area" type="text" list="{dl}" autocomplete="address-level3" placeholder="{e(q["area_ph"])}" aria-label="{e(q["step2"])}">
        <datalist id="{dl}">
{areas}
        </datalist>
        <button type="submit" class="btn qb-send">💬 {e(q["send"])}</button>
    </div>
    <p class="qb-bag" hidden></p>
    <p class="qb-fine">{e(fine)}</p>
    <p class="qb-status"><a href="{e(wa_link(q["status_msg"]))}" target="_blank" rel="noopener">{e(q["status"])}</a></p>
</form>'''


def book_href(service=None, area=None, lang="en"):
    q = {}
    if service:
        q["service"] = service
    if area:
        q["area"] = area
    base = "/hi/" if lang == "hi" else "/book/"
    return base + ("?" + urllib.parse.urlencode(q) if q else "") + "#book"


def footer_cols(ctx, indent, lang="en"):
    svc = ctx["services_by_slug"]
    s_links = "\n".join(f'{indent}            <li><a href="/services/{sl}/">{e(svc[sl]["name"])}</a></li>' for sl in ctx["services"]["footer"])
    a_links = "\n".join(f'{indent}            <li><a href="/bhopal/{slugify(n)}/">Laundry in {e(n)}</a></li>' for n in ctx["bhopal"]["footer_areas"])
    main = next(o for o in ctx["bhopal"]["outlets"] if o.get("main"))
    return f'''{indent}<div class="footer-col">
{indent}    <h4>Cleanzit</h4>
{indent}    <p>Laundry, dry cleaning, steam ironing &amp; home cleaning in Bhopal, with free doorstep pickup.</p>
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
{indent}            <li><a href="/bhopal/">All areas →</a></li>
{indent}    </ul>
{indent}</div>
{indent}<div class="footer-col">
{indent}    <h4>Contact Us</h4>
{indent}    <ul>
{indent}        <li><a href="tel:+{PHONE_ORDERS}">{PHONE_ORDERS_DISPLAY}</a> (pickups &amp; WhatsApp)</li>
{indent}        <li><a href="tel:+{PHONE_CALL}">{PHONE_CALL_DISPLAY}</a></li>
{indent}        <li><a href="mailto:{EMAIL}">{EMAIL}</a></li>
{indent}        <li>{e(full_address(main))}</li>
{indent}        <li>{e(ctx["bhopal"]["open_note"])}</li>
{indent}    </ul>
{indent}</div>
{indent}<nav class="footer-links" aria-label="More">
{indent}    <a href="/about.html">About</a>
{indent}    <a href="/pricing.html">Pricing</a>
{indent}    <a href="/stores.html">Stores</a>
{indent}    <a href="/guides/">Guides</a>
{indent}    <a href="/contact.html">Contact</a>
{indent}    <a href="/hi/" lang="hi">हिंदी</a>
{indent}    <a href="/franchise.html">Franchise enquiries</a>
{indent}</nav>
{indent_block(mobile_bar(lang), indent)}'''


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


def steps_html(ctx, mode="pickup", lang="en"):
    f = ctx["prices"].facts
    if lang == "hi":
        if mode == "home":
            steps = [("विज़िट बुक करें", "WhatsApp या कॉल पर तारीख और समय चुनें।"),
                     ("हम आपके घर आते हैं", "हमारी होम-सर्विस टीम आपके घर पर सफाई करती है।"),
                     ("साफ-सुथरा घर", "काम पूरा होने पर भुगतान करें।")]
        else:
            steps = [("पिकअप बुक करें", "फॉर्म भरें या WhatsApp / कॉल पर अपना सुविधाजनक समय बताएं।"),
                     ("हम ले जाकर साफ करते हैं", "हम आपके घर से कपड़े लेते हैं; हर कपड़े पर टैग, जांच और फैब्रिक के हिसाब से सफाई।"),
                     (f"{f['delivery_days']} दिन में डिलीवरी", f"साफ, फिनिश और पैक — ₹{f['free_pickup_min']} से ज़्यादा के ऑर्डर पर पिकअप और डिलीवरी फ्री।")]
        li = "\n".join(f"    <li><strong>{e(t)}</strong><span>{e(d)}</span></li>" for t, d in steps)
        return f'<ol class="lp-steps">\n{li}\n</ol>'
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


def price_rows_table(ctx, refs, caption, lang="en"):
    P = ctx["prices"]
    rows = "\n".join(f'            <tr><th scope="row">{e(cell_label(ctx, c, lang))}</th><td>{e(cell_display(ctx, c, lang))}</td></tr>' for c in (P.cell(r) for r in refs))
    return f'''<div class="lp-prices">
    <table>
        <caption class="sr-only">{e(caption)}</caption>
        <tbody>
{rows}
        </tbody>
    </table>
</div>'''


def home_offer_table(ctx, ids, caption, lang="en"):
    P = ctx["prices"]
    hs = P.data["home_services"]
    rows = []
    for hid in ids:
        h = P.home[hid]
        u = ctx["hi"]["unit_names"].get(h["unit"], h["unit"]) if lang == "hi" else h["unit"]
        unit = f" / {u}" if u else ""
        if P.offer_on and h["was"] != h["now"]:
            val = f'<del>{P.rupees(h["was"], False)}{unit}</del> <strong>{P.rupees(h["now"], False)}{unit}</strong>'
        else:
            val = f"{P.rupees(h['now'], True)}{unit}"
        name = f'{ctx["hi"]["item_names"].get(hid, h["name"])} (घर पर)' if lang == "hi" else f'{h["name"]} (at home)'
        rows.append(f'            <tr><th scope="row">{e(name)}</th><td>{val}</td></tr>')
        tag = "दिवाली से पहले का ऑफर — शुरुआती कीमतें" if lang == "hi" else f"{hs['label']} — starting prices"
    label = f'<p class="lp-offer-tag">🪔 {e(tag)}</p>' if P.offer_on else ""
    return f'''{label}<div class="lp-prices">
    <table>
        <caption class="sr-only">{e(caption)}</caption>
        <tbody>
{chr(10).join(rows)}
        </tbody>
    </table>
</div>'''


OPEN_NOTE = "Open 7 days a week"   # overwritten from data/bhopal.json in main()


HI_AREAS = {}   # filled from data/hi.json in main()


def outlet_card(o, closest=False, heading="h3", lang="en"):
    classes = "lp-outlet" + (" is-main" if o.get("main") else "") + (" is-closest" if closest else "")
    if lang == "hi":
        tag = "आपके सबसे पास" if closest else ("मुख्य स्टोर" if o.get("main") else "आउटलेट")
        name = f"Cleanzit {HI_AREAS.get(o['short'], o['short'])}"
        open_note, links = "हफ्ते के सातों दिन खुला", ("रास्ता और समय", "WhatsApp", "कॉल")
        wa = f"नमस्ते Cleanzit, मुझे आपके {HI_AREAS.get(o['short'], o['short'])} आउटलेट से पिकअप बुक करना है।"
    else:
        tag = "Closest to you" if closest else ("Main store" if o.get("main") else "Outlet")
        if closest and o.get("main"):
            tag += " · Main store"
        name, open_note, links = o["name"], OPEN_NOTE, ("Directions & timings", "WhatsApp", "Call")
        wa = "Hi Cleanzit, I'd like to book a pickup from your " + o["short"] + " outlet."
    photo = ""
    if o.get("photo"):
        alt = f"Cleanzit {HI_AREAS.get(o['short'], o['short'])} स्टोर" if lang == "hi" else f"Cleanzit {o['short']} store front"
        photo = f'\n    <img class="lp-outlet-photo" src="{e(o["photo"])}" alt="{e(alt)}" loading="lazy" width="480" height="360">'
    return f'''<div class="{classes}">{photo}
    <span class="lp-tag">{e(tag)}</span>
    <{heading}>{e(name)}</{heading}>
    <address>{e(full_address(o))}</address>
    <p class="lp-open">🕒 {e(open_note)}</p>
    <div class="lp-outlet-links">
        <a href="{e(maps_link(o))}" target="_blank" rel="noopener">{e(links[0])}</a>
        <a class="wa" href="{e(wa_link(wa))}" target="_blank" rel="noopener">{e(links[1])}</a>
        <a href="tel:+{PHONE_ORDERS}">{e(links[2])}</a>
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


def area_groups(ctx, per_zone=None, lang="en"):
    B = ctx["bhopal"]
    out = []
    for zone in B["zones"]:
        areas = [a for a in B["areas"] if a["zone"] == zone][:per_zone]
        if lang == "hi":
            zl = ctx["hi"]["zone_names"][zone]
            chips = "\n".join(f'        <a href="/bhopal/{slugify(a["name"])}/">{e(ctx["hi"]["area_names"][a["name"]])} में लॉन्ड्री</a>' for a in areas)
        else:
            zl = zone
            chips = "\n".join(f'        <a href="/bhopal/{slugify(a["name"])}/">Laundry in {e(a["name"])}</a>' for a in areas)
        out.append(f'<div class="lp-area-group">\n    <h3>{e(zl)}</h3>\n    <div class="lp-chips">\n{chips}\n    </div>\n</div>')
    return "\n".join(out)


def service_chips(ctx, slugs=None, label_fn=lambda s: s["name"]):
    svc = ctx["services"]["services"] if slugs is None else [ctx["services_by_slug"][x] for x in slugs]
    return "\n".join(f'    <a href="/services/{s["slug"]}/">{s["icon"]} {e(label_fn(s))}</a>' for s in svc)


def service_start(ctx, s, lang="en"):
    """Lowest price across a service's price refs and home offers -> (display, num) or None."""
    P = ctx["prices"]
    if s.get("start"):
        c = P.cell(s["start"])
    else:
        cells = [P.cell(r) for r in s["prices"]] + [P.cell("home:" + h) for h in s.get("home", [])]
        if not cells:
            return None
        c = min(cells, key=lambda c: c["num"])
    unit = c["unit"]
    if lang == "hi":
        unit = ctx["hi"]["unit_names"].get(unit, unit)
    return f"₹{c['num']:,}" + (f" / {unit}" if unit else ""), c["num"]


def clamp_desc(*parts, limit=160):
    """Join description parts, dropping trailing optional parts until it fits
    the length search engines display (~160 chars)."""
    parts = list(parts)
    while len(parts) > 1 and len(" ".join(parts)) > limit:
        parts.pop()
    return " ".join(parts)


def hreflang_links(alternates, indent="    "):
    """alternates: {"en": url, "hi": url}. English is x-default."""
    if not alternates:
        return ""
    out = [f'{indent}<link rel="alternate" hreflang="{code}-IN" href="{u}">' for code, u in sorted(alternates.items())]
    out.append(f'{indent}<link rel="alternate" hreflang="x-default" href="{alternates["en"]}">')
    return "\n".join(out)


def page_shell(ctx, *, title, description, canonical, body, ld, active, og_type="website", lang="en", alternates=None):
    lds = "\n".join(ld_script(b) for b in ld)
    alt_links = hreflang_links(alternates)
    alt_nav = (alternates or {}).get("en" if lang == "hi" else "hi", "").replace(BASE, "") or None
    hind = ('\n    <link href="https://fonts.googleapis.com/css2?family=Hind:wght@400;600;700&display=swap" rel="stylesheet">'
            if lang == "hi" else "")
    return f'''<!DOCTYPE html>
<html lang="{lang}-IN">

<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <!-- Generated by tools/build_site.py — edit data/ or content/, not this file. -->
    <title>{e(title)}</title>
    <meta name="description" content="{e(description)}">
    <link rel="canonical" href="{canonical}">
{alt_links}
    <meta name="robots" content="index, follow, max-image-preview:large, max-snippet:-1">
    <meta name="geo.region" content="IN-MP">
    <meta name="geo.placename" content="Bhopal, Madhya Pradesh">
    <meta property="og:type" content="{og_type}">
    <meta property="og:site_name" content="Cleanzit">
    <meta property="og:locale" content="{lang}_IN">
    <meta property="og:title" content="{e(title)}">
    <meta property="og:description" content="{e(description)}">
    <meta property="og:url" content="{canonical}">
    <meta property="og:image" content="{BASE}/assets/og-cleanzit.jpg">
    <meta name="twitter:card" content="summary_large_image">
    <link rel="icon" href="/assets/logo.png" type="image/png">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">{hind}
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
{nav_items(active, "                    ", lang, alt_nav)}
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
{footer_cols(ctx, "                ", lang)}
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
    <script src="/js/booking.js" defer></script>
    <script src="/js/carousel.js" defer></script>
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


def cta_pair(href, label, lang="en"):
    call = "कॉल करें" if lang == "hi" else "Call"
    return (f'                    <a class="btn" href="{e(href)}">📅 {e(label)}</a>\n'
            f'                    <a class="btn btn-outline" href="tel:+{PHONE_ORDERS}">📞 {call} {PHONE_ORDERS_DISPLAY}</a>')


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
             cta_pair(book_href(s["slug"]), "Book a Pickup" if s.get("mode") != "home" else "Book a Visit")),
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
    alternates = {"en": url, "hi": f"{BASE}/hi/services/{s['slug']}/"} if s["slug"] in ctx["hi_services"] else None
    return page_shell(ctx, title=fill(s["title"]), description=desc, canonical=url, body=body, ld=ld, active="/services.html",
                      alternates=alternates)


def build_book_page(ctx):
    P = ctx["prices"]
    url = f"{BASE}/book/"
    trail = [("Home", BASE + "/"), ("Book a Pickup", url)]
    f = P.facts
    body = "\n\n".join([
        f'''        <section class="lp-hero lp-hero-slim">
            <div class="container">
                {crumbs_html(trail)}
                <h1>Book a Free <span>Pickup</span></h1>
                <p class="lp-lede">Tick what you're sending, add your area and send — we'll reply on WhatsApp to fix a pickup time. Free pickup &amp; delivery above ₹{f["free_pickup_min"]}, delivered in {f["delivery_days"]} days, open 7 days a week.</p>
            </div>
        </section>''',
        section(f'''                <div class="book-layout">
{indent_block(quick_book(ctx), "                    ")}
                    <aside class="book-aside">
                        <h2>What happens next</h2>
{indent_block(steps_html(ctx), "                        ")}
                        <p class="lp-sub">Prefer to talk? Call <a href="tel:+{PHONE_ORDERS}">{PHONE_ORDERS_DISPLAY}</a>.</p>
                        <p class="lp-sub"><a href="/pricing.html#estimate">Estimate your bill first →</a></p>
                    </aside>
                </div>''', alt=True),
    ])
    ld = [{"@context": "https://schema.org", "@graph": [breadcrumb_ld(trail)]}]
    return page_shell(ctx, title="Book a Laundry Pickup in Bhopal | Cleanzit",
                      description=f"Book a free laundry & dry cleaning pickup in Bhopal: tick what you're sending, add your area, send on WhatsApp. Free pickup above ₹{f['free_pickup_min']}.",
                      canonical=url, body=body, ld=ld, active="/book/")


def faqs_from_html(text):
    return [(re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", q))).strip(),
             re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", a))).strip())
            for q, a in re.findall(r"<details(?![^>]*px-areas-all)[^>]*>\s*<summary[^>]*>(.*?)</summary>\s*<p[^>]*>(.*?)</p>", text, re.S)]


def build_service_hi(ctx, s, h):
    """Hindi service page: English data for prices/structure, Hindi copy from data/hi.json."""
    P = ctx["prices"]
    fill = P.fill
    f = P.facts
    url = f"{BASE}/hi/services/{s['slug']}/"
    name = ctx["hi"]["service_names"][s["slug"]]
    trail = [("होम", BASE + "/hi/"), (h["h1"], url)]
    at_home = s.get("mode") == "home"
    start = service_start(ctx, s, "hi")
    start_txt = f"{start[0]} से शुरू" if start else "कीमत के लिए पूछें"
    logistics = "पूरे भोपाल में" if at_home else f"₹{f['free_pickup_min']} से ज़्यादा पर फ्री पिकअप और डिलीवरी"
    qas = [(fill(q), fill(a)) for q, a in h["faqs"]]
    parts = []
    if s["prices"]:
        parts.append(price_rows_table(ctx, s["prices"], f"{h['h1']} — कीमतें", "hi"))
    if s.get("home"):
        parts.append(home_offer_table(ctx, s["home"], f"{h['h1']} — घर पर", "hi"))
    related = "\n".join(f'    <a href="{hi_service_href(ctx, r)}">{ctx["services_by_slug"][r]["icon"]} {e(ctx["hi"]["service_names"][r])}</a>'
                         for r in s["related"])
    body = "\n\n".join(x for x in [
        hero(trail, e(h["h1"]), e(f"{fill(h['short'])} {start_txt} · {logistics} · पहले ऑर्डर पर {f['first_order_off']}% छूट।"),
             cta_pair(book_href(s["slug"], lang="hi"), "विज़िट बुक करें" if at_home else "पिकअप बुक करें", "hi")),
        section(f'''                <h2>सर्विस के बारे में</h2>
                <div class="lp-article">
{chr(10).join(f"                <p>{e(fill(x))}</p>" for x in h["intro"])}
                <h3>क्या-क्या शामिल है</h3>
                <ul class="lp-checks">
{chr(10).join(f"                    <li>{e(fill(x))}</li>" for x in h["includes"])}
                </ul>
                </div>''', alt=True),
        section(f'''                <h2>भोपाल में {e(name)} की कीमतें</h2>
                <p class="lp-sub">“+” का मतलब है “से शुरू” — आखिरी कीमत कपड़े और उसकी हालत पर निर्भर करती है। <a href="/pricing.html">पूरी रेट लिस्ट →</a></p>
''' + "\n".join(parts)) if parts else "",
        section(f"                <h2>कैसे काम करता है</h2>\n{steps_html(ctx, s.get('mode', 'pickup'), 'hi')}", alt=True),
        section(f'''                <h2>{e(h["tips_title"])}</h2>
                <div class="lp-article">
                <ul class="lp-checks">
{chr(10).join(f"                    <li>{e(fill(x))}</li>" for x in h["tips"])}
                </ul>
                </div>'''),
        section(f"                <h2>अक्सर पूछे जाने वाले सवाल</h2>\n{faq_block(qas)}", alt=True),
        section(f'''                <h2>दूसरी सेवाएं</h2>
                <div class="lp-chips">
{related}
                </div>
                <p class="lp-sub" style="margin-top:1.5rem;"><a href="/hi/#areas">भोपाल के सभी इलाके देखें →</a></p>'''),
    ] if x)
    offers = [P.offer_ld(P.cell(r)) for r in s["prices"]] + [P.offer_ld(P.cell("home:" + x)) for x in s.get("home", [])]
    svc_ld = {"@type": "Service", "@id": url + "#service", "name": h["h1"], "serviceType": name, "inLanguage": "hi-IN",
              "description": fill(h["short"]), "url": url, "provider": ORG_REF, "areaServed": {"@type": "City", "name": "Bhopal"}}
    if offers:
        svc_ld["hasOfferCatalog"] = {"@type": "OfferCatalog", "name": f"{name} — कीमतें", "itemListElement": offers}
    ld = [{"@context": "https://schema.org", "@graph": [breadcrumb_ld(trail), svc_ld, faq_ld(qas, url)]}]
    desc = clamp_desc(f"{fill(h['short'])} {start_txt}।", f"{logistics}।", f"पहले ऑर्डर पर {f['first_order_off']}% छूट।")
    return page_shell(ctx, title=fill(h["title"]), description=desc, canonical=url, body=body, ld=ld, active="/hi/#services",
                      lang="hi", alternates={"en": f"{BASE}/services/{s['slug']}/", "hi": url})


def build_hi_home(ctx):
    url = f"{BASE}/hi/"
    body = render_template(ctx, "content/hi/home.html", lang="hi")
    qas = faqs_from_html(body)
    if not qas:
        fail("content/hi/home.html: no FAQ found")
    B = ctx["bhopal"]
    ld = [{"@context": "https://schema.org", "@graph": [
        {"@type": "WebPage", "@id": url, "url": url, "name": "भोपाल में लॉन्ड्री और ड्राई क्लीनिंग — Cleanzit", "inLanguage": "hi-IN",
         "about": ORG_REF},
        *[outlet_ld(o) for o in B["outlets"]], faq_ld(qas, url)]}]
    f = ctx["prices"].facts
    return page_shell(ctx, title="भोपाल में लॉन्ड्री और ड्राई क्लीनिंग | फ्री पिकअप | Cleanzit",
                      description=ctx["prices"].fill("भोपाल में लॉन्ड्री, ड्राई क्लीनिंग और प्रेस — {p:wash-fold:price}/किलो से। ₹{fact:free_pickup_min} से ज़्यादा पर फ्री पिकअप, {fact:delivery_days} दिन में डिलीवरी, पहले ऑर्डर पर {fact:first_order_off}% छूट।"),
                      canonical=url, body=body, ld=ld, active="/hi/", lang="hi", alternates={"en": f"{BASE}/", "hi": url})


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
             cta_pair(book_href(), "Book a Pickup")),
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
        "image": f"{BASE}/assets/og-cleanzit.jpg"}]
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
             cta_pair(book_href(), "Book a Pickup")),
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
    qas = [
        ("Where are Cleanzit's laundry outlets in Bhopal?",
         "Cleanzit's outlets in Bhopal: " + "; ".join(f"{o['short']} — {full_address(o)}" for o in B["outlets"]) + "."),
        ("Do you offer free laundry pickup and delivery in Bhopal?",
         f"Yes. Pickup and delivery are free on orders above ₹{f['free_pickup_min']}. Book on WhatsApp at {PHONE_ORDERS_DISPLAY} and we'll collect from your door."),
        ("How much does laundry cost in Bhopal?",
         P.fill("Wash & Fold is {p:wash-fold:price} per kg and Wash & Steam Iron is {p:wash-iron:price} per kg. Shirt dry cleaning is {p:shirt:dry}. New customers get {fact:first_order_off}% off their first order.")),
        ("How long does laundry and dry cleaning take?",
         f"Standard delivery is within {f['delivery_days']} days for laundry, dry cleaning, woolens, household items and shoes."),
        ("Are Cleanzit outlets open on Sunday?",
         "Yes — every Cleanzit outlet in Bhopal is open 7 days a week, including Sunday. Check each outlet's timings on Google Maps, or book a pickup any day on WhatsApp."),
        ("Which areas of Bhopal does Cleanzit cover?",
         "Free doorstep pickup and delivery across Bhopal — " + "; ".join(
             z + ": " + ", ".join(a["name"] for a in B["areas"] if a["zone"] == z) for z in B["zones"]) + "."),
    ]
    outlets = "\n".join(outlet_card(o) for o in B["outlets"])
    lede = P.fill("Cleanzit outlets across Bhopal and free doorstep pickup &amp; delivery on orders above ₹{fact:free_pickup_min}. "
                  "Laundry {p:wash-fold:price}/kg, shirt dry cleaning {p:shirt:dry}, delivered in {fact:delivery_days} days — and {fact:first_order_off}% off your first order.")
    body = "\n\n".join([
        hero(trail, "Laundry &amp; Dry Cleaning in <span>Bhopal</span>", lede,
             cta_pair(book_href(), "Book a Pickup")),
        section(f'''                <h2>Our Outlets in Bhopal</h2>
                <p class="lp-sub">Drop in at any outlet, or let us come to you — every outlet runs free pickup &amp; delivery.</p>
                <div class="lp-outlets">
{outlets}
                </div>''', alt=True, id_="outlets"),
        section(f'''                <h2>📍 Areas We Serve in Bhopal</h2>
                <p class="lp-sub">Free doorstep pickup &amp; delivery across Bhopal. Pick your area for local details and your closest outlet.</p>
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
                      description="Cleanzit laundry & dry cleaning in Bhopal — stores in Gulmohar, Shahpura, Bagmugaliya, Kolar. " + P.fill("Wash & fold {p:wash-fold:price}/kg, free pickup above ₹{fact:free_pickup_min}, {fact:first_order_off}% off first order."),
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
         f"{where}, at {full_address(o)}. You can also drop off at any Cleanzit outlet in Bhopal."),
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
             cta_pair(book_href(area=slugify(name)), f"Book a Pickup in {name}")),
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
    """'Build your laundry bag' estimator: category tabs + a bill styled as a
    Cleanzit garment tag. Arithmetic lives in js/estimator.js."""
    P = ctx["prices"]
    f = P.facts
    tabs, panels = [], []
    for gi, grp in enumerate(P.data["calculator"]):
        gid = f"bag-{slugify(grp['group'])}"
        tabs.append(f'    <button type="button" role="tab" class="bag-tab" aria-controls="{gid}" aria-selected="{"true" if gi == 0 else "false"}">'
                    f'{grp["icon"]} {e(grp["group"])} <span class="bag-count" hidden>0</span></button>')
        rows = []
        for ref in grp["items"]:
            c = P.cell(ref)
            it = c["item"]
            cat = P.cat_of[it["id"]]
            col = ref.split(":")[1]
            kind = cat["columns"][col] if len(cat["columns"]) > 1 else ""
            unit_word = "kg" if c["unit"] == "kg" else ""
            rows.append(f'''        <li class="bag-item" data-label="{e(c["label"])}" data-price="{c["num"]}" data-from="{1 if c["plus"] else 0}" data-unit="{e(c["unit"])}">
            <span class="bag-name">{e(it["name"])}{f' <small>{e(kind.lower())}</small>' if kind else ""}</span>
            <span class="bag-price">{e(c["display"])}</span>
            <span class="bag-step">
                <button type="button" data-step="-1" aria-label="Remove one: {e(c["label"])}">−</button>
                <output>0</output>{f'<i>{unit_word}</i>' if unit_word else ""}
                <button type="button" data-step="1" aria-label="Add one: {e(c["label"])}">+</button>
            </span>
        </li>''')
        panels.append(f'    <ul class="bag-list" id="{gid}" role="tabpanel">\n' + "\n".join(rows) + "\n    </ul>")
    return f'''<h2>Build Your Laundry Bag</h2>
<p class="lp-sub">Pick what you're sending — your bill updates as you go, and you can book with the same list.</p>
<div class="bag" data-free-min="{f["free_pickup_min"]}" data-first-off="{f["first_order_off"]}">
<div class="bag-picker">
    <div class="bag-tabs" role="tablist" aria-label="Item categories">
{chr(10).join(tabs)}
    </div>
{chr(10).join(panels)}
</div>
<aside class="bag-tag" aria-live="polite">
    <div class="tag-head"><span class="tag-hole" aria-hidden="true"></span>Cleanzit · your bill</div>
    <ul class="tag-lines"><li class="tag-empty">Your bag is empty — add items to see your bill.</li></ul>
    <dl class="tag-sums">
        <div><dt>Subtotal</dt><dd data-out="sub">₹0</dd></div>
        <div><dt>First order −{f["first_order_off"]}%</dt><dd data-out="disc">−₹0</dd></div>
        <div class="tag-total"><dt>First order total</dt><dd data-out="total">₹0</dd></div>
    </dl>
    <div class="tag-meter" role="img" aria-label="Progress towards free pickup"><span data-out="meter"></span></div>
    <p class="tag-pickup" data-out="pickup">Add ₹{f["free_pickup_min"]} of items for free pickup</p>
    <p class="tag-note">“+” = starting price; the final bill depends on fabric and condition. Returning customers pay the subtotal.</p>
    <a class="btn tag-cta" data-out="cta" href="/book/#book">Book pickup with this bag →</a>
</aside>
</div>
<noscript><p class="lp-sub">Turn on JavaScript to use the bill builder — or see the full price list above.</p></noscript>
<script src="/js/estimator.js" defer></script>'''


# ============================================================ other hand-written page regions
def service_grid(ctx, slugs, detailed, lang="en"):
    cards = []
    for sl in slugs:
        s = ctx["services_by_slug"][sl]
        st = service_start(ctx, s, lang)
        if lang == "hi":
            price = f"{st[0]} से शुरू" if st else "कीमत के लिए पूछें"
            name, href = ctx["hi"]["service_names"][sl], hi_service_href(ctx, sl)
        else:
            price = f"Starting {st[0]}" if st else "Ask for a quote"
            name, href = s["name"], f"/services/{sl}/"
        blurb = f"\n        <p>{e(ctx['prices'].fill(s['short']))}</p>" if detailed else ""
        more = '\n        <span class="lp-more">Learn more →</span>' if detailed else ""
        cards.append(f'''    <a class="lp-service{' is-detailed' if detailed else ''}" href="{href}">
        <span class="lp-service-icon" aria-hidden="true">{s["icon"]}</span>
        <h3>{e(name)}</h3>{blurb}
        <strong>{e(price)}</strong>{more}
    </a>''')
    return '<div class="lp-service-grid">\n' + "\n".join(cards) + "\n</div>"


TONES = ["#E6FBFB", "#FFF3E0", "#EEF0FF", "#E9F8EF", "#FDECEF", "#EAF4FF", "#FFF8DB"]


def service_scroller(ctx, lang="en"):
    """Sideways-scrolling service cards (arrows + progress bar in js/carousel.js).
    A service may set "image" in data/services.json to show a real photo."""
    hi = ctx["hi"]
    cards = []
    # Cards with a real photo lead; the rest show a line icon.
    ordered = sorted(ctx["services"]["services"], key=lambda sv: not sv.get("image"))
    for i, sv in enumerate(ordered):
        st = service_start(ctx, sv, lang)
        if lang == "hi":
            name, href = hi["service_names"][sv["slug"]], hi_service_href(ctx, sv["slug"])
            price = f"{st[0]} से शुरू" if st else "कीमत के लिए पूछें"
            meta = "पूरे भोपाल में"
        else:
            name, href = sv["name"], f"/services/{sv['slug']}/"
            price = f"Starting {st[0]}" if st else "Ask for a quote"
            meta = ctx["prices"].fill(sv["short"])
        if sv.get("image"):
            visual = f'<img src="{e(sv["image"])}" alt="{e(sv.get("image_alt", ""))}" loading="lazy" width="480" height="360">'
        else:
            visual = glyph(SERVICE_GLYPH[sv["slug"]])
        cls = "px-visual is-photo" if sv.get("image") else "px-visual"
        cards.append(f'''        <li class="px-card">
            <a href="{href}">
                <div class="{cls}" style="--tone: {TONES[i % len(TONES)]}">{visual}</div>
                <div class="px-body">
                    <h3>{e(name)}</h3>
                    <p class="px-meta">{e(meta)}</p>
                    <p class="px-price">{e(price)}</p>
                </div>
            </a>
        </li>''')
    prev_l, next_l = ("पिछला", "अगला") if lang == "hi" else ("Previous", "Next")
    return f'''<div class="px-scroller">
    <button type="button" class="px-arrow px-prev" aria-label="{prev_l}">‹</button>
    <ul class="px-track">
{chr(10).join(cards)}
    </ul>
    <button type="button" class="px-arrow px-next" aria-label="{next_l}">›</button>
    <div class="px-track-bar" aria-hidden="true"><span></span></div>
</div>'''


def offer_slide(ctx, lang="en"):
    """Third hero slide: the seasonal home-cleaning offer while it runs, else the first-order discount."""
    P = ctx["prices"]
    f = P.facts
    if P.offer_on:
        if lang == "hi":
            t, d, cta, href = ("दिवाली से पहले: घर की सफाई पर 50% तक छूट", "सोफा, कारपेट, गद्दे, पर्दे और किचन की सफाई — आपके घर पर।",
                               "घर की सफाई देखें", hi_service_href(ctx, "home-deep-cleaning-bhopal"))
        else:
            t, d, cta, href = ("Pre-Diwali: up to 50% off home cleaning", "Sofa, carpet, mattress, curtain and kitchen cleaning — at your home.",
                               "See home cleaning", "/services/home-deep-cleaning-bhopal/")
    else:
        if lang == "hi":
            t, d, cta, href = (f"पहले ऑर्डर पर {f['first_order_off']}% छूट", "Cleanzit पर नए हैं? आपके पहले ऑर्डर पर छूट अपने-आप मिलती है।", "पिकअप बुक करें", "#book")
        else:
            t, d, cta, href = (f"{f['first_order_off']}% off your first order", "New to Cleanzit? Your first order is discounted automatically.", "Book your first pickup", "#book")
    alts = (("Cleanzit काउंटर पर ऑर्डर लेते हुए", "पैक किए हुए साफ कपड़े") if lang == "hi"
            else ("Weighing an order at the Cleanzit counter", "Cleaned clothes packed for delivery"))
    return f'''            <article class="px-slide" aria-roledescription="slide">
                <div class="px-copy">
                    <h2 class="px-title">{e(t)}</h2>
                    <p>{e(d)}</p>
                    <a class="btn px-cta" href="{href}">{e(cta)}</a>
                </div>
                <div class="px-photos">
                    <img src="/assets/photos/hero-counter.webp" alt="{e(alts[0])}" width="350" height="400" loading="lazy">
                    <img src="/assets/photos/hero-packed.webp" alt="{e(alts[1])}" width="350" height="400" loading="lazy">
                </div>
            </article>'''


def guides_html(ctx):
    cards = "\n".join(f'''    <a class="lp-card" href="/guides/{g["slug"]}/">
        <strong>{e(g["h1"])}</strong>
        <span>{e(g["description"])}</span>
    </a>''' for g in ctx["guides"])
    return f'<div class="lp-cards">\n{cards}\n</div>'


def render_template(ctx, path, extra=None, lang="en"):
    """content/*.html template -> HTML: {{component}} tokens, then price placeholders."""
    raw = open(os.path.join(ROOT, path), encoding="utf-8").read()
    raw = re.sub(r"^\s*<!--.*?-->\s*\n", "", raw, count=1, flags=re.S)
    B = ctx["bhopal"]
    all_slugs = [x["slug"] for x in ctx["services"]["services"]]
    comps = {
        "quick_book": lambda: indent_block(quick_book(ctx, lang), "                "),
        "service_scroller": lambda: indent_block(service_scroller(ctx, lang), "                "),
        "offer_slide": lambda: offer_slide(ctx, lang),
        "services_grid": lambda: indent_block(service_grid(ctx, all_slugs if lang == "hi" else ctx["services"]["home_page"], False, lang), "                "),
        "steps": lambda: indent_block(steps_html(ctx, lang=lang), "                "),
        "areas": lambda: indent_block(area_groups(ctx, lang=lang), "                "),
        "outlets": lambda: indent_block('<div class="lp-outlets">\n' + "\n".join(outlet_card(o, lang=lang) for o in B["outlets"]) + "\n</div>", "                "),
        "guides": lambda: indent_block(guides_html(ctx), "                "),
    }
    comps.update(extra or {})
    def sub(m):
        name = m.group(1)
        if name not in comps:
            fail(f"{path}: unknown component {{{{{name}}}}}")
        return comps[name]()
    return ctx["prices"].fill(re.sub(r"\{\{(\w+)\}\}", sub, raw)).rstrip("\n")


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
                 "stores.html": "/stores.html", "contact.html": "/contact.html", "franchise.html": ""}


def visible_faqs(page):
    """Question/answer pairs exactly as shown in a hand-written page's <details>
    blocks, so its FAQPage markup can never drift from what visitors see."""
    s = open(os.path.join(ROOT, page), encoding="utf-8").read()
    qas = []
    for q, a in re.findall(r"<summary[^>]*>(.*?)</summary>\s*<p[^>]*>(.*?)</p>", s, re.S):
        clean = lambda x: re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", x))).replace("▼", "").strip()
        qas.append((clean(q), clean(a)))
    if not qas:
        fail(f"{page}: no FAQ found for faq-ld")
    return qas


def fill_static_pages(ctx):
    B = ctx["bhopal"]
    outlets_ld = {"@context": "https://schema.org", "@graph": [outlet_ld(o) for o in B["outlets"]]}
    for p in STATIC_PAGES:
        replace_region(p, "nav", lambda ind, p=p: nav_items(STATIC_ACTIVE[p], ind))
        replace_region(p, "footer", lambda ind: footer_cols(ctx, ind))
    replace_region("stores.html", "outlets", lambda ind: indent_block("\n".join(outlet_card(o, heading="h2") for o in B["outlets"]), ind))
    replace_region("stores.html", "outlets-ld", lambda ind: ld_script(outlets_ld, ind))
    replace_region("index.html", "outlets-ld", lambda ind: ld_script(outlets_ld, ind))
    replace_region("index.html", "home-main", lambda ind: render_template(ctx, "content/home.html"))
    replace_region("services.html", "service-cards", lambda ind: indent_block(service_grid(ctx, [s["slug"] for s in ctx["services"]["services"]], True), ind))
    panels = {"laundry": panel_laundry, "men": lambda c: panel_table(c, "men"), "women": lambda c: panel_table(c, "women"),
              "woolen": lambda c: panel_table(c, "woolen"), "household": lambda c: panel_table(c, "household"),
              "shoesbags": panel_shoesbags, "homeservices": panel_home, "membership": panel_membership}
    for pid, fn in panels.items():
        replace_region("pricing.html", f"panel-{pid}", lambda ind, fn=fn: indent_block(fn(ctx), ind))
    replace_region("pricing.html", "pricing-ld", lambda ind: ld_script(pricing_ld(ctx), ind))
    for page, anchor in (("index.html", ""), ("contact.html", "contact.html"), ("franchise.html", "franchise.html")):
        replace_region(page, "faq-ld", lambda ind, page=page, anchor=anchor: ld_script({"@context": "https://schema.org", **faq_ld(visible_faqs(page), f"{BASE}/{anchor}")}, ind))
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
        out += ["", "Hindi (हिंदी):", f"- Hindi homepage: {BASE}/hi/"]
        out += [f"- {h['h1']}: {BASE}/hi/services/{h['slug']}/" for h in ctx["hi"]["services"]]
        out += ["", f"Book a pickup: {BASE}/book/", f"Full price list: {BASE}/pricing.html", f"Bhopal outlets and areas: {BASE}/bhopal/"]
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
    global OPEN_NOTE
    OPEN_NOTE = bhopal["open_note"]
    guides = load_guides(prices)
    hi = load("data/hi.json")
    HI_AREAS.update(hi["area_names"])
    ctx = {"prices": prices, "services": services, "bhopal": bhopal, "guides": guides, "hi": hi,
           "hi_services": {h["slug"]: h for h in hi["services"]},
           "services_by_slug": {s["slug"]: s for s in services["services"]},
           "guides_by_slug": {g["slug"]: g for g in guides},
           "outlets_by_id": {o["id"]: o for o in bhopal["outlets"]}}

    # ---- validate cross-references before writing anything
    check_booking_groups(ctx)
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
    for grp in prices.data["calculator"]:
        for ref in grp["items"]:
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
    for a in bhopal["areas"]:
        if a["name"] not in hi["area_names"]:
            fail(f"data/hi.json: no Hindi name for area {a['name']!r}")
    for z in bhopal["zones"]:
        if z not in hi["zone_names"]:
            fail(f"data/hi.json: no Hindi name for zone {z!r}")
    for sv in services["services"]:
        if sv["slug"] not in hi["service_names"]:
            fail(f"data/hi.json: no Hindi name for service {sv['slug']!r}")
    for h in hi["services"]:
        if h["slug"] not in svc:
            fail(f"data/hi.json: Hindi page for unknown service {h['slug']!r}")
        base = svc[h["slug"]]
        for r in base["prices"]:
            iid = r.split(":")[0]
            if iid not in hi["item_names"]:
                fail(f"data/hi.json: no Hindi name for price item {iid!r} (used on {h['slug']})")

    # ---- pages
    urls = [(f"{BASE}/", "1.0"), (f"{BASE}/pricing.html", "0.9"), (f"{BASE}/services.html", "0.9"),
            (f"{BASE}/stores.html", "0.7"), (f"{BASE}/about.html", "0.5"), (f"{BASE}/contact.html", "0.6"),
            (f"{BASE}/franchise.html", "0.4")]
    for s in services["services"]:
        write(f"services/{s['slug']}/index.html", build_service(ctx, s))
        urls.append((f"{BASE}/services/{s['slug']}/", "0.8"))
    write("services/index.html", build_services_redirect())
    write("book/index.html", build_book_page(ctx))
    urls.append((f"{BASE}/book/", "0.8"))
    write("hi/index.html", build_hi_home(ctx))
    urls.append((f"{BASE}/hi/", "0.8"))
    for h in hi["services"]:
        write(f"hi/services/{h['slug']}/index.html", build_service_hi(ctx, svc[h["slug"]], h))
        urls.append((f"{BASE}/hi/services/{h['slug']}/", "0.7"))
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
               + prune("hi/services", set(ctx["hi_services"]))
               + prune("bhopal", set(slugs)))

    check_handwritten_prices(ctx)
    fill_static_pages(ctx)
    fill_llms(ctx)
    write_sitemap(ctx, urls)
    print(f"built {len(services['services'])} service pages, {len(guides)} guides, Bhopal hub + {len(bhopal['areas'])} areas "
          f"+ {len(hi['services']) + 1} Hindi pages ({removed} stale removed); refreshed {len(STATIC_PAGES)} hand-written pages + llms.txt; sitemap.xml has {len(urls)} URLs")


if __name__ == "__main__":
    main()
