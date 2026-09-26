# Cleanzit India — laundryfranchise

This repository (`chaisngmydream06021990/laundryfranchise`) is the **live
CleanZit website**, published at **www.cleanzit.co.in** (see `CNAME`). It is
a static, multi-page site — no build step, no framework — with two audiences:

1. **Customers in Bhopal** — laundry, dry cleaning, steam ironing and home
   deep-cleaning. Full price list is in `pricing.html`.
2. **Prospective franchise partners** across India — `index.html` and
   `contact.html`'s FAQ cover investment, ROI and training.

Do not confuse this with the other `laundry-konnect*` repos on this GitHub
account (`laundry-konnect`, `laundry-konnect2`, `laundry-konnect3`) — those
are earlier/separate single-page sites for a different presentation of the
same business. This repo (`laundryfranchise`) is the current one in active
use.

## Structure

- `index.html`, `about.html`, `services.html`, `pricing.html`,
  `stores.html`, `contact.html` — the six pages, sharing `header`/`footer`
  markup (no templating — edits to nav/footer must be repeated per page).
- `css/styles.css` — single stylesheet, CSS custom properties in `:root`.
- `js/app.js` — page interactions (mobile nav, pincode checker, WhatsApp
  form redirect, scroll reveal).
- `js/offers-banner.js` — **single source of truth for the site-wide
  announcement bar** shown on every page. Change the `OFFER` object there
  to update the offer text everywhere at once; see the comment at the top
  of the file for wiring details.
- `robots.txt`, `sitemap.xml`, `llms.txt` — crawler/AI-assistant surfaces.
  Keep `llms.txt` and the JSON-LD `OfferCatalog` blocks in `index.html` /
  `pricing.html` in sync with the visible price tables whenever prices
  change — mismatches read as untrustworthy data to both crawlers and
  customers who check both.

## Bhopal outlets & area pages (generated)

`data/bhopal.json` is the single source of truth for the Bhopal outlets
(addresses, Google rating) and the list of areas served. Each area has a
`zone` (one of `zones`; controls grouping on the hub/homepage and each
page's "Nearby Areas"), an `outlet` (its closest outlet id) and an optional
`aka` (alternate name people search for, e.g. Bairagarh → Sant Hirdaram
Nagar). `footer_areas` picks the six areas linked in every footer. After
editing it, run:

    python3 tools/build_bhopal_pages.py

which (standard library only, safe to re-run) regenerates:

- `bhopal/index.html` — hub listing every outlet and area
- `bhopal/<area-slug>/index.html` — one page per area, with its closest
  outlet, prices, FAQ and nearby areas (pages for areas removed from the
  data file are deleted)
- `sitemap.xml`
- the `<!-- BEGIN:gen:NAME --> … <!-- END:gen:NAME -->` regions inside the
  hand-written pages: outlet cards + outlet JSON-LD in `stores.html`,
  area links (capped at 6 per zone) + outlet JSON-LD in `index.html`, the
  "Laundry in Bhopal" footer column on all six pages, and the area list in
  `llms.txt`.

Never hand-edit generated files or anything between gen markers — it is
overwritten on the next run. Generated pages use root-absolute paths
(`/css/styles.css`), which work on the www.cleanzit.co.in custom domain;
preview them with `python3 -m http.server` from the repo root, not
file://.

## Prices

The price list in `pricing.html` (six tabs: Laundry, Men's Wear, Women's
Wear, Woolen, Household, Shoes & Bags, plus **Home Services** and
**Membership**) is the source of truth for current pricing. When prices
change, update, in this order:

1. The visible `<table>`/panel in `pricing.html`.
2. The matching `OfferCatalog` entries in the JSON-LD `<script>` block in
   `pricing.html`'s `<head>`.
3. `llms.txt` at the repo root, and `headline_prices` in
   `data/bhopal.json` (then re-run the generator).
4. Any FAQ answer in `contact.html` (and its FAQPage JSON-LD, generated
   from that same visible text) that quotes a specific price.

The "Home Services" tab reflects a **seasonal Pre-Diwali offer** (up to 50%
off). Update or remove it, and its struck-through prices, once the
campaign ends — see the comment above that panel in `pricing.html`.

## Known inconsistencies (pre-existing, not yet reconciled)

- Contact email in JSON-LD/footers is `franchise@cleanzit.in` (`.in`, not
  `.co.in`) — this predates recent edits and hasn't been verified either
  way; don't "fix" it without confirming which domain is correct.
- Opening hours: `stores.html`/`contact.html` historically said
  "Mon-Sat 9 AM - 8 PM", but Google Maps shows the outlets open on Sunday
  (10–10:30 AM). Hours were deliberately left out of the outlet cards and
  JSON-LD (they link to Google Maps for timings) until confirmed.
- Pincodes: only the Gulmohar outlet's (462039) is known; the others are
  blank in `data/bhopal.json` — fill them in when available.
