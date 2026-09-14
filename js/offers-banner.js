/**
 * offers-banner.js
 * ------------------------------------------------------------
 * Single source of truth for the site-wide announcement bar.
 * Edit the OFFER object below to change what shows on EVERY page
 * (index, about, services, pricing, stores, contact) — nothing
 * else needs to change.
 *
 * Include as the very first thing inside <body>, before <header>:
 *   <body>
 *     <script src="js/offers-banner.js"></script>
 *     <noscript>...</noscript>   (static fallback, see below)
 *     <header>...
 *
 * Uses document.write so the banner is present before first paint
 * (no flash / layout jump) — safe here because this script tag is
 * always the first synchronous thing in <body>.
 * ------------------------------------------------------------
 */
(function () {
  'use strict';

  var OFFER = {
    // Shown on every page. Keep it short — it's one line on desktop.
    text: '20% OFF your first order',
    // Second clause, separated by a middle dot.
    text2: 'FREE pickup & delivery above ₹300',
    // Phone shown as a tel: link at the end.
    phone: '7777818187',
    phoneDisplay: '77778 18187',
    // WhatsApp deep link used by the phone number.
    whatsappUrl: 'https://wa.me/917777818187?text=Hi%2C%20I%27d%20like%20to%20book%20a%20pickup.'
  };

  var html =
    '<div class="offer-banner" id="offer-banner" role="region" aria-label="Current offer">' +
      '<span><strong>' + OFFER.text + '</strong> &nbsp;·&nbsp; ' + OFFER.text2 +
      ' &nbsp;·&nbsp; <a href="' + OFFER.whatsappUrl + '" target="_blank" rel="noopener">Book now: ' +
      OFFER.phoneDisplay + '</a></span>' +
      '<button type="button" class="offer-banner-close" aria-label="Dismiss offer banner" onclick="' +
        'document.body.classList.add(\'offer-banner-hidden\');' +
        'try{sessionStorage.setItem(\'cleanzitOfferBannerDismissed\',\'1\')}catch(e){}' +
      '">✕</button>' +
    '</div>';

  var dismissed = false;
  try {
    dismissed = sessionStorage.getItem('cleanzitOfferBannerDismissed') === '1';
  } catch (e) {
    // Private browsing / storage blocked — just show the banner.
  }

  if (dismissed) {
    document.write('<script>document.documentElement.setAttribute("data-offer-banner","hidden")<\/script>');
    // Still write the banner (for non-JS-adjacent consistency) but mark body to hide it via CSS on DOMContentLoaded.
    document.write(html);
    document.addEventListener('DOMContentLoaded', function () {
      document.body.classList.add('offer-banner-hidden');
    });
  } else {
    document.write(html);
  }
})();
