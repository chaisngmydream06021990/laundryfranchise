/**
 * Two-tap pickup booking (markup from tools/build_site.py, quick_book()).
 * 1) tap a service (optional)  2) type an area (optional)  -> WhatsApp.
 * Name and number come from WhatsApp itself, so we never ask for them.
 * Pre-fills from ?service=<slug>&area=<slug>&items=<bag from the estimator>.
 */
(function () {
  'use strict';

  function fill(tpl, vals) {
    return tpl.replace(/\{(\w+)\}/g, function (_, k) { return vals[k] || ''; });
  }

  Array.prototype.forEach.call(document.querySelectorAll('.qb'), function (form) {
    var params = new URLSearchParams(window.location.search);
    var more = form.querySelector('.qb-more');
    var extras = form.querySelectorAll('.qb-extra');
    var bagEl = form.querySelector('.qb-bag');

    function showExtras() {
      Array.prototype.forEach.call(extras, function (el) { el.hidden = false; });
      if (more) more.hidden = true;
    }
    if (more) more.addEventListener('click', showExtras);

    var slug = params.get('service');
    if (slug) {
      var radio = form.querySelector('input[name="service"][data-slug="' + slug.replace(/[^a-z0-9-]/g, '') + '"]');
      if (radio) {
        radio.checked = true;
        if (radio.closest('.qb-extra')) showExtras();
      }
    }
    var areaSlug = params.get('area');
    if (areaSlug) {
      var opt = form.querySelector('datalist option[data-slug="' + areaSlug.replace(/[^a-z0-9-]/g, '') + '"]');
      if (opt) form.elements.area.value = opt.value;
    }
    var bag = params.get('items');
    if (bag) {
      bagEl.textContent = form.getAttribute('data-bag') + ': ' + bag;
      bagEl.hidden = false;
    }
    if ((slug || areaSlug || bag) && window.location.hash !== '#book') {
      form.scrollIntoView({ block: 'center' });
    }

    form.addEventListener('submit', function (ev) {
      ev.preventDefault();
      var checked = form.querySelector('input[name="service"]:checked');
      var vals = { service: checked ? checked.value : '', area: String(form.elements.area.value || '').trim() };
      var key = vals.service && vals.area ? 'full' : vals.service ? 'service' : vals.area ? 'area' : 'none';
      var msg = fill(form.getAttribute('data-msg-' + key), vals);
      if (bag) msg += '\n\n' + form.getAttribute('data-bag') + ': ' + bag;
      var url = 'https://wa.me/' + form.getAttribute('data-wa') + '?text=' + encodeURIComponent(msg);
      // 'noopener' would make window.open return null and trigger the fallback,
      // so detach the opener manually instead.
      var win = window.open(url, '_blank');
      if (win) { win.opener = null; } else { window.location.href = url; }
    });
  });
})();
