/**
 * Hero slides (.px-hero) and sideways service row (.px-scroller).
 * Markup comes from content/home.html + tools/build_site.py.
 */
(function () {
  'use strict';
  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // ---- Hero slides with progress bars
  Array.prototype.forEach.call(document.querySelectorAll('.px-hero'), function (hero) {
    var slides = hero.querySelectorAll('.px-slide');
    var bars = hero.querySelectorAll('.px-bar');
    var pause = hero.querySelector('.px-pause');
    if (slides.length < 2) return;
    var DURATION = 6000;
    var current = 0, start = 0, elapsed = 0, playing = !reduce, raf = null;

    function show(i) {
      current = (i + slides.length) % slides.length;
      Array.prototype.forEach.call(slides, function (s, j) {
        s.classList.toggle('is-active', j === current);
        s.setAttribute('aria-hidden', j === current ? 'false' : 'true');
        Array.prototype.forEach.call(s.querySelectorAll('a,button'), function (el) {
          if (j === current) el.removeAttribute('tabindex'); else el.setAttribute('tabindex', '-1');
        });
      });
      Array.prototype.forEach.call(bars, function (b, j) {
        b.classList.toggle('is-done', j < current);
        b.setAttribute('aria-current', j === current ? 'true' : 'false');
        b.firstElementChild.style.width = j < current ? '100%' : '0%';
      });
      elapsed = 0;
      start = performance.now();
    }

    function tick(now) {
      if (playing) {
        var t = elapsed + (now - start);
        var bar = bars[current] && bars[current].firstElementChild;
        if (bar) bar.style.width = Math.min(100, t / DURATION * 100) + '%';
        if (t >= DURATION) show(current + 1);
      }
      raf = requestAnimationFrame(tick);
    }

    function setPlaying(p) {
      if (p && !playing) { start = performance.now(); }
      if (!p && playing) { elapsed += performance.now() - start; }
      playing = p;
      if (pause) {
        pause.textContent = playing ? '❚❚' : '▶';
        pause.setAttribute('aria-pressed', playing ? 'false' : 'true');
      }
    }

    Array.prototype.forEach.call(bars, function (b, j) {
      b.addEventListener('click', function () { show(j); });
    });
    if (pause) pause.addEventListener('click', function () { setPlaying(!playing); });
    // Pause while the visitor is reading or using the slide
    hero.addEventListener('mouseenter', function () { if (playing) { setPlaying(false); hero.dataset.hoverPaused = '1'; } });
    hero.addEventListener('mouseleave', function () { if (hero.dataset.hoverPaused) { delete hero.dataset.hoverPaused; setPlaying(true); } });
    hero.addEventListener('focusin', function () { if (playing) setPlaying(false); });

    show(0);
    setPlaying(playing);
    raf = requestAnimationFrame(tick);
  });

  // ---- Sideways scrolling cards with arrows + progress bar
  Array.prototype.forEach.call(document.querySelectorAll('.px-scroller'), function (sc) {
    var track = sc.querySelector('.px-track');
    var prev = sc.querySelector('.px-prev');
    var next = sc.querySelector('.px-next');
    var bar = sc.querySelector('.px-track-bar span');
    if (!track) return;

    function update() {
      var max = track.scrollWidth - track.clientWidth;
      var ratio = max > 0 ? track.scrollLeft / max : 1;
      var visible = track.scrollWidth ? track.clientWidth / track.scrollWidth : 1;
      if (bar) {
        bar.style.width = Math.max(visible * 100, 8) + '%';
        bar.style.marginLeft = (ratio * (100 - Math.max(visible * 100, 8))) + '%';
      }
      if (prev) prev.disabled = track.scrollLeft <= 2;
      if (next) next.disabled = track.scrollLeft >= max - 2;
    }
    function page(dir) {
      track.scrollBy({ left: dir * track.clientWidth * 0.85, behavior: reduce ? 'auto' : 'smooth' });
    }
    if (prev) prev.addEventListener('click', function () { page(-1); });
    if (next) next.addEventListener('click', function () { page(1); });
    track.addEventListener('scroll', update, { passive: true });
    window.addEventListener('resize', update);
    update();
  });
})();
