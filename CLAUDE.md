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

Static site, no framework. Six hand-written pages (`index.html`, `about.html`,
`services.html`, `pricing.html`, `stores.html`, `contact.html`) plus generated
folders. One stylesheet (`css/styles.css`), `js/app.js` (nav, pincode checker,
forms), `js/offers-banner.js` (site-wide offer bar — edit its `OFFER` object),
`js/estimator.js` (price estimator on pricing.html).

## Everything data-driven is built by one script

    python3 tools/build_site.py

Standard library only; deterministic (a re-run with unchanged sources changes
nothing); run it after editing any source below, then commit the output.

| Source | Controls |
|---|---|
| `data/prices.json` | **Every price** — pricing.html tabs, JSON-LD and estimator, all service pages, "Starting ₹X" cards, Bhopal pages, `llms.txt`. `facts` = free-pickup minimum, delivery days, first-order discount. Items marked `"source": "site"` aren't on the printed price list — confirm them. |
| `data/services.json` | Service pages at `/services/<slug>/`, cards on services.html and the homepage, footer service links. Text uses `{p:ITEM:COL}`, `{now:HOME_ID}`, `{was:HOME_ID}`, `{fact:KEY}` placeholders so prices are never typed twice. |
| `data/bhopal.json` | Outlets (addresses), city zones, 67 areas → `/bhopal/` and `/bhopal/<area>/`, outlet cards/JSON-LD on stores.html + index.html, footer area links. |
| `content/guides/*.html` | Guides at `/guides/<slug>/` — a `<!--meta {json} -->` header then plain HTML. Add a file to add a guide. |

Hand-written pages contain `<!-- BEGIN:gen:NAME -->…<!-- END:gen:NAME -->`
regions (nav, footer, price panels, cards, JSON-LD). Never edit inside them —
they're overwritten. Generated pages and folders (`services/`, `guides/`,
`bhopal/`, `sitemap.xml`, parts of `llms.txt`) must not be hand-edited either.

The build fails loudly on broken references (unknown price id, missing guide,
etc.) and if a hand-written page quotes a `₹N/kg` figure that isn't a real
per-kg price. Other prices quoted in hand-written prose (homepage, contact
FAQ) still need a manual check when prices change.

Generated pages use root-absolute paths (`/css/styles.css`); preview with
`python3 -m http.server` from the repo root, not file://.

## Content rules (important for search engines and AI assistants)

- Only state facts the business has confirmed (posters, the site's own About
  and Services pages). Don't invent guarantees, turnaround times, equipment or
  capacity claims.
- **Never publish ratings or review counts that aren't real**, and don't add
  `aggregateRating` markup — Google ignores self-served business reviews, and
  inflated figures are misleading to customers.
- FAQ structured data must match an FAQ actually visible on the same page.
- Keep one name per price item (e.g. "Men's suit (2 pcs)" vs "Women's suit
  (2 pcs)") so tables and structured data never show two identical labels
  with different prices.

## Known inconsistencies (pre-existing, not yet reconciled)

- Contact email in JSON-LD/footers is `franchise@cleanzit.in` (`.in`, not
  `.co.in`) — this predates recent edits and hasn't been verified either
  way; don't "fix" it without confirming which domain is correct.
- `services.html` "How It Works" says "Book via app" — confirm an app exists.
- Homepage stats (10,000 families, 1,000,000 garments, 99% satisfaction) are
  pre-existing claims; confirm or soften them.
- Opening hours: `stores.html`/`contact.html` historically said
  "Mon-Sat 9 AM - 8 PM", but Google Maps shows the outlets open on Sunday
  (10–10:30 AM). Hours were deliberately left out of the outlet cards and
  JSON-LD (they link to Google Maps for timings) until confirmed.
- Pincodes: only the Gulmohar outlet's (462039) is known; the others are
  blank in `data/bhopal.json` — fill them in when available.
