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
`js/estimator.js` (price estimator on pricing.html), `js/booking.js` (two-tap
WhatsApp booking), `js/carousel.js` (homepage hero slides + service scroller).

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
| `content/home.html` | The homepage body (everything inside `<main>` on index.html). Uses the price placeholders plus `{{components}}` (quick_book, service_scroller, offer_slide, steps, areas, outlets, guides). Layout is inspired by priceless.com: auto-advancing hero slides with progress bars, a horizontal service scroller, light section headings. Hero images in `assets/slide-*.webp` are stock images cropped to hide other brands' signage — replace with real Cleanzit photos when available (a service can also take an `"image"` field for its scroller card). |
| `data/hi.json` + `content/hi/home.html` | Hindi: `/hi/` homepage and `/hi/services/<slug>/` pages (Hindi copy in `services`), Hindi names for services, zones, areas and price items. The build fails if an area/zone/service lacks a Hindi name. English↔Hindi pages carry reciprocal hreflang links. |

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

## Customer journey

- Booking is **two taps**: pick a service chip (optional), type an area
  (optional), send on WhatsApp. No name, phone, address, date or time fields —
  WhatsApp already gives us the customer's number and we agree the slot in
  the chat. There is **no app**, only WhatsApp.
- Every "Book" button goes to the quick-book form (`/book/`, the homepage
  `#book`, or `/hi/#book`), passing `?service=<slug>&area=<slug>` so it arrives
  pre-selected. Markup comes from `quick_book()` in the build script; the first
  8 services show as chips and the rest sit behind "+ More".
- The pricing page's "Build your laundry bag" estimator hands its item list to
  the quick-book form via `?items=` and is appended to the WhatsApp message.
- On phones a sticky Call / WhatsApp / Book bar replaces the floating button.
- `js/app.js` handles only `#contact-form` and `#franchise-form`.
- Don't show outlet or area counts ("4 outlets", "67 areas") — the owner
  found them confusing. The homepage links to `/bhopal/` instead of listing
  every area; the main nav is just Services, Pricing, Stores, Contact.
- Franchise is deliberately secondary: `franchise.html`, linked from the
  footer, the stores page and a small homepage band — not the main nav.

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
- Still unverified owner claims kept on the site: franchise figures (₹8 lakh entry, 12–18 month ROI, 70–80% margin, 6 months royalty-free).
- Dropped in the homepage redesign (unverified): "10,000+ happy families", "German Tech … enzymes". Removed as unsupported: "99% satisfaction", "1,000,000 garments", placeholder
  franchisee testimonials (Pune/Hyderabad/Delhi — Cleanzit is Bhopal-only),
  "customers love the app", "200% returns", "24h express" (express = same day
  for an extra charge, per the FAQ).
- Opening hours: confirmed open 7 days a week (`open_note` in
  data/bhopal.json). Exact times per outlet aren't known yet, so they're not in
  the structured data — add `openingHoursSpecification` once confirmed.
- Pincodes: only the Gulmohar outlet's (462039) is known; the others are
  blank in `data/bhopal.json` — fill them in when available.
