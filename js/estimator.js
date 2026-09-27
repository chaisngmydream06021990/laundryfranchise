/**
 * "Build your laundry bag" on pricing.html. Markup and prices come from
 * tools/build_site.py (data/prices.json); this file does the tabs, the
 * arithmetic, the itemised bill, and hands the bag to the booking form
 * via /book/?items=...
 */
(function () {
  'use strict';
  var bag = document.querySelector('.bag');
  if (!bag) return;

  var freeMin = Number(bag.getAttribute('data-free-min')) || 0;
  var firstOff = Number(bag.getAttribute('data-first-off')) || 0;
  var tabs = Array.prototype.slice.call(bag.querySelectorAll('.bag-tab'));
  var lists = Array.prototype.slice.call(bag.querySelectorAll('.bag-list'));
  var items = Array.prototype.slice.call(bag.querySelectorAll('.bag-item'));
  var linesEl = bag.querySelector('.tag-lines');
  var emptyEl = bag.querySelector('.tag-empty');
  var out = {};
  Array.prototype.forEach.call(bag.querySelectorAll('[data-out]'), function (el) {
    out[el.getAttribute('data-out')] = el;
  });

  function rupees(n) { return '₹' + Math.round(n).toLocaleString('en-IN'); }

  // Tabs: show one category at a time (all stay visible without JS).
  function select(i) {
    tabs.forEach(function (t, j) {
      t.setAttribute('aria-selected', i === j ? 'true' : 'false');
      lists[j].hidden = i !== j;
    });
  }
  tabs.forEach(function (t, i) { t.addEventListener('click', function () { select(i); }); });
  select(0);

  function update() {
    var sub = 0, anyFrom = false, summary = [];
    linesEl.querySelectorAll('.tag-line').forEach(function (li) { li.remove(); });

    items.forEach(function (it) {
      var qty = Number(it.getAttribute('data-qty')) || 0;
      if (!qty) return;
      var price = Number(it.getAttribute('data-price'));
      var kg = it.getAttribute('data-unit') === 'kg';
      var from = it.getAttribute('data-from') === '1';
      var cost = qty * price;
      sub += cost;
      if (from) anyFrom = true;
      var label = it.getAttribute('data-label');
      var qtyText = kg ? qty + ' kg' : qty + ' ×';
      var li = document.createElement('li');
      li.className = 'tag-line';
      li.innerHTML = '<span></span><b></b>';
      li.firstChild.textContent = qtyText + ' ' + label;
      li.lastChild.textContent = rupees(cost) + (from ? '+' : '');
      linesEl.appendChild(li);
      summary.push(qtyText + ' ' + label);
    });

    // Per-tab counts
    lists.forEach(function (list, j) {
      var n = 0;
      list.querySelectorAll('.bag-item').forEach(function (it) { n += Number(it.getAttribute('data-qty')) || 0; });
      var badge = tabs[j].querySelector('.bag-count');
      badge.textContent = n;
      badge.hidden = !n;
    });

    var plus = anyFrom ? '+' : '';
    var disc = sub * firstOff / 100;
    emptyEl.hidden = sub > 0;
    out.sub.textContent = rupees(sub) + plus;
    out.disc.textContent = '−' + rupees(disc);
    out.total.textContent = rupees(sub - disc) + plus;

    var pct = freeMin ? Math.min(100, sub / freeMin * 100) : 100;
    out.meter.style.width = pct + '%';
    bag.classList.toggle('is-free', sub >= freeMin && sub > 0);
    out.pickup.textContent = !sub ? 'Add ' + rupees(freeMin) + ' of items for free pickup'
      : sub >= freeMin ? '✓ Free pickup & delivery unlocked'
      : rupees(freeMin - sub) + ' more for free pickup & delivery';

    var href = '/book/';
    if (summary.length) {
      href += '?items=' + encodeURIComponent(summary.join(', ') + ' (estimate ' + rupees(sub) + plus + ')');
    }
    out.cta.setAttribute('href', href + '#book');
  }

  items.forEach(function (it) {
    var output = it.querySelector('output');
    it.addEventListener('click', function (ev) {
      var btn = ev.target.closest('button[data-step]');
      if (!btn) return;
      var qty = Math.min(99, Math.max(0, (Number(it.getAttribute('data-qty')) || 0) + Number(btn.getAttribute('data-step'))));
      it.setAttribute('data-qty', qty);
      output.textContent = qty;
      it.classList.toggle('has-qty', qty > 0);
      update();
    });
  });
  update();
})();
