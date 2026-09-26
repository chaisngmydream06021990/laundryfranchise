#!/usr/bin/env python3
"""
Build the Bhopal location pages from data/bhopal.json.

    python3 tools/build_bhopal_pages.py

Writes / refreshes:
  bhopal/index.html                 hub: all outlets + every area we serve
  bhopal/<area-slug>/index.html     one landing page per area
  sitemap.xml                       static pages + all of the above
and rewrites the regions between <!-- BEGIN:gen:NAME --> / <!-- END:gen:NAME -->
markers in the hand-written pages:
  stores.html   gen:outlets, gen:outlets-ld
  index.html    gen:areas, gen:outlets-ld
  every page    gen:footer-bhopal

Standard library only. Re-running is safe: output is deterministic and
area pages that are no longer in the data file are deleted.
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
PHONE_ORDERS = "917777818187"          # WhatsApp / pickups
PHONE_ORDERS_DISPLAY = "+91 77778 18187"
PHONE_CALL = "917777818188"            # calls / franchise
PHONE_CALL_DISPLAY = "+91 77778 18188"
STATIC_PAGES = ["index.html", "pricing.html", "services.html", "stores.html", "about.html", "contact.html"]

e = html.escape


# ---------------------------------------------------------------- helpers
def slugify(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def wa_link(text):
    return f"https://wa.me/{PHONE_ORDERS}?text=" + urllib.parse.quote(text)


def maps_link(outlet):
    q = f"Cleanzit Dry Clean & Laundry Service, {outlet['street']}, Bhopal"
    return "https://www.google.com/maps/search/?api=1&query=" + urllib.parse.quote(q)


def full_address(o):
    pin = f" {o['postalCode']}" if o.get("postalCode") else ""
    return f"{o['street']}, Bhopal, Madhya Pradesh{pin}"


def outlet_ld(o):
    addr = {
        "@type": "PostalAddress",
        "streetAddress": o["street"],
        "addressLocality": "Bhopal",
        "addressRegion": "Madhya Pradesh",
        "addressCountry": "IN",
    }
    if o.get("postalCode"):
        addr["postalCode"] = o["postalCode"]
    return {
        "@type": ["DryCleaningOrLaundry", "LocalBusiness"],
        "@id": f"{BASE}/#outlet-{o['id']}",
        "name": o["name"],
        "url": f"{BASE}/stores.html",
        "telephone": "+91-7777818187",
        "image": f"{BASE}/assets/logo.png",
        "priceRange": "Rs 15 - Rs 1599",
        "currenciesAccepted": "INR",
        "address": addr,
        "hasMap": maps_link(o),
        "areaServed": {"@type": "City", "name": "Bhopal"},
        "parentOrganization": {"@id": f"{BASE}/#organization"},
    }


def ld_script(obj, indent="    "):
    body = json.dumps(obj, indent=2, ensure_ascii=False)
    body = "\n".join(indent + line for line in body.splitlines())
    return f'{indent}<script type="application/ld+json">\n{body}\n{indent}</script>'


def stars(rating):
    r = float(rating)
    full = int(r)
    half = 1 if r - full >= 0.5 else 0
    return "★" * full + ("½" if half else "") + "☆" * (5 - full - half)


# ------------------------------------------------------ shared fragments
def outlet_card(o, closest=False, heading="h3"):
    classes = "lp-outlet" + (" is-main" if o.get("main") else "") + (" is-closest" if closest else "")
    tag = "Main store" if o.get("main") else "Outlet"
    if closest:
        tag = "Closest to you" + (" · Main store" if o.get("main") else "")
    rating = ""
    if o.get("google_rating"):
        rating = (f'<p class="lp-rating"><span class="stars" aria-hidden="true">{stars(o["google_rating"])}</span> '
                  f'{e(o["google_rating"])} on Google ({o["google_reviews"]} reviews)</p>')
    return f'''<div class="{classes}">
    <span class="lp-tag">{e(tag)}</span>
    <{heading}>{e(o["name"])}</{heading}>
    <address>{e(full_address(o))}</address>
    {rating}
    <div class="lp-outlet-links">
        <a href="{e(maps_link(o))}" target="_blank" rel="noopener">Directions &amp; timings</a>
        <a class="wa" href="{e(wa_link("Hi Cleanzit, I'd like to book a pickup from your " + o["short"] + " outlet."))}" target="_blank" rel="noopener">WhatsApp</a>
        <a href="tel:+{PHONE_ORDERS}">Call</a>
    </div>
</div>'''


def area_groups(data, link_prefix="/bhopal/", per_zone=None):
    """Area links grouped by city zone. per_zone caps each group (homepage)."""
    by_zone = {z: [] for z in data["zones"]}
    for a in data["areas"]:
        by_zone[a["zone"]].append(a)
    out = []
    for zone in data["zones"]:
        areas = by_zone[zone][:per_zone] if per_zone else by_zone[zone]
        if not areas:
            continue
        chips = "\n".join(f'        <a href="{link_prefix}{slugify(a["name"])}/">Laundry in {e(a["name"])}</a>' for a in areas)
        out.append(f'''<div class="lp-area-group">
    <h3>{e(zone)}</h3>
    <div class="lp-chips">
{chips}
    </div>
</div>''')
    return "\n".join(out)


def price_table(data):
    rows = "\n".join(f"            <tr><th scope=\"row\">{e(k)}</th><td>{e(v)}</td></tr>" for k, v in data["headline_prices"])
    return f'''<div class="lp-prices">
    <table>
        <caption style="position:absolute;left:-9999px;">Popular Cleanzit prices in Bhopal</caption>
        <tbody>
{rows}
        </tbody>
    </table>
</div>'''


STEPS = '''<ol class="lp-steps">
    <li><strong>Book a pickup</strong><span>WhatsApp or call us with a time that suits you.</span></li>
    <li><strong>We collect &amp; clean</strong><span>Our rider picks up from your door; every item is tagged and billed upfront.</span></li>
    <li><strong>Delivered in 3 days</strong><span>Cleaned, pressed and packed — free delivery on orders above ₹300.</span></li>
</ol>'''


def faq_block(qas):
    items = "\n".join(
        f'    <details>\n        <summary>{e(q)}</summary>\n        <p>{e(a)}</p>\n    </details>' for q, a in qas)
    return f'<div class="lp-faq">\n{items}\n</div>'


def faq_ld(qas, page_url):
    return {
        "@type": "FAQPage",
        "@id": page_url + "#faq",
        "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in qas],
    }


def footer_bhopal_col(data):
    lis = "\n".join(f'                        <li><a href="/bhopal/{slugify(n)}/">Laundry in {e(n)}</a></li>' for n in data["footer_areas"])
    return f'''                <div class="footer-col">
                    <h4>Laundry in Bhopal</h4>
                    <ul>
                        <li><a href="/bhopal/">All Bhopal areas &amp; outlets</a></li>
{lis}
                    </ul>
                </div>'''


def llms_areas(data):
    lines = ["Free pickup and delivery across these Bhopal areas (each has its own page",
             "at https://www.cleanzit.co.in/bhopal/<area>/):", ""]
    for z in data["zones"]:
        lines.append(f"- {z}: " + ", ".join(
            a["name"] + (f" ({a['aka']})" if a.get("aka") else "") for a in data["areas"] if a["zone"] == z))
    return "\n".join(lines)


def page_shell(*, title, description, canonical, body, ld_blocks, footer_col):
    ld = "\n".join(ld_script(b) for b in ld_blocks)
    return f'''<!DOCTYPE html>
<html lang="en-IN">

<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <!-- Generated by tools/build_bhopal_pages.py from data/bhopal.json — edit those, not this file. -->
    <title>{e(title)}</title>
    <meta name="description" content="{e(description)}">
    <link rel="canonical" href="{canonical}">
    <meta name="robots" content="index, follow, max-image-preview:large, max-snippet:-1">
    <meta name="geo.region" content="IN-MP">
    <meta name="geo.placename" content="Bhopal, Madhya Pradesh">
    <meta property="og:type" content="website">
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
{ld}
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
                <img src="/assets/logo.png" alt="Cleanzit Logo" style="height: 60px;">
            </a>
            <div class="mobile-toggle" aria-label="Toggle Navigation">☰</div>
            <nav>
                <ul class="nav-links">
                    <li><a href="/about.html">About</a></li>
                    <li><a href="/services.html">Services</a></li>
                    <li><a href="/pricing.html">Pricing</a></li>
                    <li><a href="/stores.html">Stores</a></li>
                    <li><a href="/contact.html">Contact</a></li>
                    <li><a href="tel:+{PHONE_CALL}" class="nav-phone">📞 {PHONE_CALL_DISPLAY}</a></li>
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
                <div class="footer-col">
                    <h4>Cleanzit</h4>
                    <p>Laundry, dry cleaning &amp; home cleaning in Bhopal — and India's happiest laundry franchise.</p>
                </div>
                <div class="footer-col">
                    <h4>Quick Links</h4>
                    <ul>
                        <li><a href="/about.html">About Us</a></li>
                        <li><a href="/services.html">Services</a></li>
                        <li><a href="/pricing.html">Pricing</a></li>
                        <li><a href="/stores.html">Stores</a></li>
                    </ul>
                </div>
{footer_col}
                <div class="footer-col">
                    <h4>Contact Us</h4>
                    <ul>
                        <li><a href="tel:+{PHONE_ORDERS}">{PHONE_ORDERS_DISPLAY}</a> (pickups)</li>
                        <li><a href="tel:+{PHONE_CALL}">{PHONE_CALL_DISPLAY}</a></li>
                        <li><a href="mailto:franchise@cleanzit.in">franchise@cleanzit.in</a></li>
                    </ul>
                </div>
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


# ----------------------------------------------------------------- pages
def build_hub(data):
    url = f"{BASE}/bhopal/"
    outlets = "\n".join(outlet_card(o) for o in data["outlets"])
    n_out, n_areas = len(data["outlets"]), len(data["areas"])
    qas = [
        ("Where are Cleanzit's laundry outlets in Bhopal?",
         "Cleanzit has " + str(n_out) + " outlets in Bhopal: " + "; ".join(f"{o['short']} — {full_address(o)}" for o in data["outlets"]) + "."),
        ("Do you offer free laundry pickup and delivery in Bhopal?",
         f"Yes. Pickup and delivery is free on orders above ₹300. Book on WhatsApp at {PHONE_ORDERS_DISPLAY} and a rider will collect from your door."),
        ("How much does laundry cost in Bhopal?",
         "Wash & Fold is ₹60 per kg and Wash & Steam Iron is ₹90 per kg. Dry cleaning starts at ₹60 for a shirt or trouser. New customers get 20% off their first order."),
        ("How long does laundry and dry cleaning take?",
         "Standard delivery is within 3 days for laundry, dry cleaning, woolens, household items and shoes."),
        ("Which areas of Bhopal does Cleanzit cover?",
         "Free doorstep pickup and delivery across Bhopal — " + "; ".join(
             z + ": " + ", ".join(a["name"] for a in data["areas"] if a["zone"] == z) for z in data["zones"]) + "."),
    ]
    body = f'''        <section class="lp-hero">
            <div class="container">
                <p class="lp-crumbs"><a href="/">Home</a> › Bhopal</p>
                <h1>Laundry &amp; Dry Cleaning in <span>Bhopal</span></h1>
                <p class="lp-lede">{n_out} Cleanzit outlets across Bhopal and free doorstep pickup &amp; delivery on orders above ₹300. Laundry from ₹60/kg, dry cleaning from ₹60, delivered in 3 days — and 20% off your first order.</p>
                <div class="lp-ctas">
                    <a class="btn" href="{e(wa_link("Hi Cleanzit, I'd like to book a laundry pickup in Bhopal."))}" target="_blank" rel="noopener">💬 Book a Pickup</a>
                    <a class="btn btn-outline" href="/pricing.html">See Price List</a>
                </div>
            </div>
        </section>

        <section class="lp-section alt" id="outlets">
            <div class="container">
                <h2>Our Outlets in Bhopal</h2>
                <p class="lp-sub">Drop in at any outlet, or let us come to you — every outlet runs free pickup &amp; delivery.</p>
                <div class="lp-outlets">
{outlets}
                </div>
            </div>
        </section>

        <section class="lp-section" id="areas">
            <div class="container">
                <h2>📍 Areas We Serve in Bhopal</h2>
                <p class="lp-sub">Free doorstep pickup &amp; delivery across {n_areas} neighbourhoods. Pick your area for local details and your closest outlet.</p>
{area_groups(data)}
                <p class="lp-sub" style="margin-top:1rem;">Don't see your area? <a href="{e(wa_link("Hi Cleanzit, do you pick up from my area in Bhopal?"))}" target="_blank" rel="noopener">Ask us on WhatsApp</a> — we'll confirm the same day.</p>
            </div>
        </section>

        <section class="lp-section alt">
            <div class="container">
                <h2>Popular Prices</h2>
                <p class="lp-sub">Transparent, itemised pricing. <a href="/pricing.html">See the full price list →</a></p>
{price_table(data)}
            </div>
        </section>

        <section class="lp-section">
            <div class="container">
                <h2>How It Works</h2>
                <p class="lp-sub">No app, no queue.</p>
{STEPS}
            </div>
        </section>

        <section class="lp-section alt">
            <div class="container">
                <h2>Frequently Asked Questions</h2>
{faq_block(qas)}
            </div>
        </section>'''
    ld = [{
        "@context": "https://schema.org",
        "@graph": [
            {"@type": "BreadcrumbList", "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "Home", "item": BASE + "/"},
                {"@type": "ListItem", "position": 2, "name": "Bhopal", "item": url}]},
            *[outlet_ld(o) for o in data["outlets"]],
            {"@type": "ItemList", "name": "Areas served in Bhopal", "itemListElement": [
                {"@type": "ListItem", "position": i + 1, "name": f"Laundry in {a['name']}, Bhopal",
                 "url": f"{BASE}/bhopal/{slugify(a['name'])}/"} for i, a in enumerate(data["areas"])]},
            faq_ld(qas, url),
        ],
    }]
    return page_shell(
        title="Laundry & Dry Cleaning in Bhopal | Free Pickup | Cleanzit",
        description=f"Cleanzit — laundry & dry cleaning in Bhopal with {n_out} outlets (Gulmohar, Shahpura, Bagmugaliya, Kolar). Wash & fold ₹60/kg, free pickup & delivery above ₹300, 3-day delivery, 20% off first order.",
        canonical=url, body=body, ld_blocks=ld, footer_col=footer_bhopal_col(data))


def build_area(data, area, outlets_by_id):
    name = area["name"]
    slug = slugify(name)
    url = f"{BASE}/bhopal/{slug}/"
    o = outlets_by_id[area["outlet"]]
    others = [x for x in data["outlets"] if x["id"] != o["id"]]
    nearby = [a for a in data["areas"] if a["zone"] == area["zone"] and a["name"] != name]
    aka = area.get("aka")
    aka_note = f" (also known as {aka})" if aka else ""
    nearby_chips = "\n".join(f'                    <a href="/bhopal/{slugify(a["name"])}/">Laundry in {e(a["name"])}</a>' for a in nearby)
    other_cards = "\n".join(outlet_card(x) for x in others)
    at_outlet = o["locality"].lower() == name.lower()
    where = (f"Our {o['short']} outlet is right here in {name}" if at_outlet
             else f"Your closest outlet is Cleanzit {o['short']}")
    qas = [
        (f"Do you offer laundry pickup in {name}, Bhopal?",
         f"Yes. Cleanzit picks up and delivers across {name}{aka_note}, free on orders above ₹300. Book on WhatsApp at {PHONE_ORDERS_DISPLAY} with your address and a preferred time."),
        (f"Which Cleanzit outlet is closest to {name}?",
         f"{where}, at {full_address(o)}. You can also drop off at any of our {len(data['outlets'])} Bhopal outlets."),
        (f"How much does dry cleaning cost in {name}?",
         "Same prices across Bhopal: shirt or trouser dry cleaning ₹60, 2-piece suit ₹200, saree from ₹120. Laundry is ₹60/kg (wash & fold) or ₹90/kg (wash & steam iron). New customers get 20% off the first order."),
        (f"How long does delivery take in {name}?",
         f"Standard delivery in {name} is within 3 days for laundry, dry cleaning, woolens, household items and shoes."),
    ]
    body = f'''        <section class="lp-hero">
            <div class="container">
                <p class="lp-crumbs"><a href="/">Home</a> › <a href="/bhopal/">Bhopal</a> › {e(name)}</p>
                <h1>Laundry &amp; Dry Cleaning in <span>{e(name)}</span>, Bhopal</h1>
                <p class="lp-lede">Free doorstep pickup &amp; delivery in {e(name)}{e(aka_note)} on orders above ₹300. {e(where)} — laundry from ₹60/kg, dry cleaning from ₹60, back to you in 3 days. 20% off your first order.</p>
                <div class="lp-ctas">
                    <a class="btn" href="{e(wa_link(f"Hi Cleanzit, I'd like to book a laundry pickup in {name}, Bhopal."))}" target="_blank" rel="noopener">💬 Book a Pickup in {e(name)}</a>
                    <a class="btn btn-outline" href="tel:+{PHONE_ORDERS}">📞 Call {PHONE_ORDERS_DISPLAY}</a>
                </div>
            </div>
        </section>

        <section class="lp-section alt">
            <div class="container">
                <h2>Your Closest Cleanzit Outlet</h2>
                <p class="lp-sub">Drop off in person, or book a pickup and our rider comes to you in {e(name)}.</p>
                <div class="lp-outlets" style="max-width:520px;">
{outlet_card(o, closest=True)}
                </div>
            </div>
        </section>

        <section class="lp-section">
            <div class="container">
                <h2>Prices in {e(name)}</h2>
                <p class="lp-sub">Same transparent prices at every Cleanzit outlet. <a href="/pricing.html">Full price list →</a></p>
{price_table(data)}
            </div>
        </section>

        <section class="lp-section alt">
            <div class="container">
                <h2>How Pickup Works in {e(name)}</h2>
                <p class="lp-sub">Laundry, dry cleaning, steam ironing, shoe cleaning, and sofa/carpet/mattress cleaning at home.</p>
{STEPS}
            </div>
        </section>

        <section class="lp-section">
            <div class="container">
                <h2>Frequently Asked Questions</h2>
{faq_block(qas)}
            </div>
        </section>

        <section class="lp-section alt">
            <div class="container">
                <h2>Nearby Areas</h2>
                <p class="lp-sub">Other areas in {e(area["zone"])} we pick up from.</p>
                <div class="lp-chips">
{nearby_chips}
                </div>
                <p class="lp-center"><a class="btn btn-outline" href="/bhopal/">All Bhopal areas &amp; outlets</a></p>
            </div>
        </section>

        <section class="lp-section">
            <div class="container">
                <h2>Other Cleanzit Outlets in Bhopal</h2>
                <div class="lp-outlets">
{other_cards}
                </div>
            </div>
        </section>'''
    ld = [{
        "@context": "https://schema.org",
        "@graph": [
            {"@type": "BreadcrumbList", "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "Home", "item": BASE + "/"},
                {"@type": "ListItem", "position": 2, "name": "Bhopal", "item": BASE + "/bhopal/"},
                {"@type": "ListItem", "position": 3, "name": name, "item": url}]},
            {"@type": "Service",
             "@id": url + "#service",
             "name": f"Laundry & dry cleaning in {name}, Bhopal",
             "serviceType": "Laundry, dry cleaning and steam ironing with free pickup and delivery",
             "areaServed": {"@type": "Place", "name": f"{name}, Bhopal, Madhya Pradesh"},
             "provider": outlet_ld(o),
             "offers": {"@type": "Offer", "priceCurrency": "INR", "price": "60", "unitText": "per kg",
                        "description": "Wash & Fold from Rs 60/kg; free pickup & delivery above Rs 300"}},
            faq_ld(qas, url),
        ],
    }]
    return slug, page_shell(
        title=f"Laundry & Dry Cleaning in {name}, Bhopal | Free Pickup | Cleanzit",
        description=f"Laundry & dry cleaning in {name}{aka_note}, Bhopal with free pickup & delivery above ₹300. Closest outlet: Cleanzit {o['short']}. Wash & fold ₹60/kg, dry clean from ₹60, 3-day delivery, 20% off first order.",
        canonical=url, body=body, ld_blocks=ld, footer_col=footer_bhopal_col(data))


# ------------------------------------------- regions in hand-written pages
def replace_region(path, name, content):
    s = open(path, encoding="utf-8").read()
    # The name must end at whitespace or "-->", so gen:outlets never matches gen:outlets-ld.
    pat = re.compile(r"(<!-- BEGIN:gen:%s(?:\s[^>]*)?-->)(.*?)(^[ \t]*<!-- END:gen:%s -->)" % (re.escape(name), re.escape(name)), re.S | re.M)
    if len(pat.findall(s)) != 1:
        sys.exit(f"{path}: expected exactly one gen:{name} region")
    s = pat.sub(lambda m: m.group(1) + "\n" + content + "\n" + m.group(3), s, count=1)
    open(path, "w", encoding="utf-8").write(s)


def outlets_ld_block(data):
    return ld_script({"@context": "https://schema.org", "@graph": [outlet_ld(o) for o in data["outlets"]]})


def write_sitemap(data):
    today = datetime.date.today().isoformat()
    urls = [(f"{BASE}/", "1.0")] + [(f"{BASE}/{p}", "0.8" if p == "pricing.html" else "0.6") for p in STATIC_PAGES if p != "index.html"]
    urls.append((f"{BASE}/bhopal/", "0.9"))
    urls += [(f"{BASE}/bhopal/{slugify(a['name'])}/", "0.7") for a in data["areas"]]
    items = "\n".join(f"  <url>\n    <loc>{u}</loc>\n    <lastmod>{today}</lastmod>\n    <priority>{p}</priority>\n  </url>" for u, p in urls)
    open(os.path.join(ROOT, "sitemap.xml"), "w", encoding="utf-8").write(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<!-- Generated by tools/build_bhopal_pages.py -->\n'
        f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{items}\n</urlset>\n')
    return len(urls)


def main():
    data = json.load(open(os.path.join(ROOT, "data", "bhopal.json"), encoding="utf-8"))
    outlets_by_id = {o["id"]: o for o in data["outlets"]}
    names = {a["name"] for a in data["areas"]}
    for a in data["areas"]:
        if a["outlet"] not in outlets_by_id:
            sys.exit(f"area {a['name']!r} references unknown outlet {a['outlet']!r}")
        if a["zone"] not in data["zones"]:
            sys.exit(f"area {a['name']!r} has unknown zone {a['zone']!r} (add it to 'zones')")
    for n in data["footer_areas"]:
        if n not in names:
            sys.exit(f"footer_areas entry {n!r} is not an area")
    slugs = [slugify(a["name"]) for a in data["areas"]]
    if len(set(slugs)) != len(slugs):
        sys.exit("two areas produce the same URL slug")

    bhopal_dir = os.path.join(ROOT, "bhopal")
    os.makedirs(bhopal_dir, exist_ok=True)
    open(os.path.join(bhopal_dir, "index.html"), "w", encoding="utf-8").write(build_hub(data))

    for a in data["areas"]:
        slug, page = build_area(data, a, outlets_by_id)
        d = os.path.join(bhopal_dir, slug)
        os.makedirs(d, exist_ok=True)
        open(os.path.join(d, "index.html"), "w", encoding="utf-8").write(page)

    # Remove pages for areas deleted from the data file.
    removed = 0
    for entry in os.listdir(bhopal_dir):
        p = os.path.join(bhopal_dir, entry)
        if os.path.isdir(p) and entry not in slugs:
            shutil.rmtree(p)
            removed += 1

    # Regions inside the hand-written pages.
    cards = "\n".join(outlet_card(o, heading="h2") for o in data["outlets"])
    replace_region(os.path.join(ROOT, "stores.html"), "outlets", cards)
    replace_region(os.path.join(ROOT, "stores.html"), "outlets-ld", outlets_ld_block(data))
    replace_region(os.path.join(ROOT, "index.html"), "outlets-ld", outlets_ld_block(data))
    replace_region(os.path.join(ROOT, "index.html"), "areas", area_groups(data, per_zone=6))
    replace_region(os.path.join(ROOT, "llms.txt"), "areas", llms_areas(data))
    for p in STATIC_PAGES:
        replace_region(os.path.join(ROOT, p), "footer-bhopal", footer_bhopal_col(data))

    n = write_sitemap(data)
    print(f"built bhopal/ hub + {len(data['areas'])} area pages ({removed} stale removed); "
          f"refreshed stores.html, index.html, footers; sitemap.xml has {n} URLs")


if __name__ == "__main__":
    main()
