/**
 * Two-step pickup booking (markup from tools/build_site.py, quick_book()).
 * 1) tick what you're sending — any number of tiles, or none
 * 2) type an area (optional)  -> WhatsApp.
 * Name and number come from WhatsApp itself, so we never ask for them.
 * Pre-fills from ?service=<slug>&area=<slug>&items=<bag from the estimator>:
 * a service slug ticks its tile and names that service in the message.
 */
(function () {
  'use strict';

  Array.prototype.forEach.call(document.querySelectorAll('.qb'), function (form) {
    var params = new URLSearchParams(window.location.search);
    var names = {};
    try { names = JSON.parse(form.getAttribute('data-names') || '{}'); } catch (err) { names = {}; }
    var boxes = Array.prototype.slice.call(form.querySelectorAll('input[name="need"]'));
    var bagEl = form.querySelector('.qb-bag');

    // A specific service from a service page's "Book" link, e.g. sofa cleaning.
    var slug = (params.get('service') || '').replace(/[^a-z0-9-]/g, '');
    if (slug) {
      boxes.forEach(function (box) {
        if ((' ' + box.getAttribute('data-services') + ' ').indexOf(' ' + slug + ' ') !== -1) {
          box.checked = true;
          if (names[slug]) box.setAttribute('data-detail', names[slug]);
        }
      });
    }
    var areaSlug = (params.get('area') || '').replace(/[^a-z0-9-]/g, '');
    if (areaSlug) {
      var opt = form.querySelector('datalist option[data-slug="' + areaSlug + '"]');
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
      var picked = boxes.filter(function (b) { return b.checked; }).map(function (b) {
        var detail = b.getAttribute('data-detail');
        return detail && detail !== b.value ? b.value + ' (' + detail + ')' : b.value;
      });
      var area = String(form.elements.area.value || '').trim();
      var lines = [form.getAttribute('data-intro')];
      if (picked.length) lines.push(form.getAttribute('data-for') + ': ' + picked.join(', '));
      if (area) lines.push(form.getAttribute('data-area') + ': ' + area);
      if (bag) lines.push('', form.getAttribute('data-bag') + ': ' + bag);
      var url = 'https://wa.me/' + form.getAttribute('data-wa') + '?text=' + encodeURIComponent(lines.join('\n'));
      // 'noopener' would make window.open return null and trigger the fallback,
      // so detach the opener manually instead.
      var win = window.open(url, '_blank');
      if (win) { win.opener = null; } else { window.location.href = url; }
    });
  });
})();
