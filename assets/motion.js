/* ============================================================================
   motion.js — runtime for the site-wide motion layer (vanilla, dependency-free)

   Effects: scroll-reveal/stagger, count-up numbers, cursor spotlight on cards,
   click ripple, magnetic chat launcher, confetti on real achievement unlocks.

   Safety first: the whole thing is wrapped in try/catch; if anything throws, or
   IntersectionObserver is missing, or motion is reduced, we reveal everything
   immediately so content is NEVER stuck hidden.
   ========================================================================== */
(function () {
  var VI = (window.VI = window.VI || {});
  var html = document.documentElement;
  html.classList.add("vi-motion");
  html.setAttribute("data-vi-ready", "1"); // tells the head no-flash guard the runtime booted

  var reduce = false, touch = false;
  try {
    reduce = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
    touch = (window.matchMedia && matchMedia("(hover: none)").matches) || "ontouchstart" in window;
  } catch (e) {}

  function revealAll() {
    [].forEach.call(document.querySelectorAll("[data-reveal]"), function (el) { el.classList.add("is-in"); });
  }

  // ----------------------------------------------------------- scroll reveal
  var io = null;
  function ensureIO() {
    if (io || !("IntersectionObserver" in window)) return io;
    io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (en.isIntersecting) { en.target.classList.add("is-in"); io.unobserve(en.target); }
      });
    }, { rootMargin: "0px 0px -8% 0px", threshold: 0.05 });
    return io;
  }
  function observeReveals(root) {
    var obs = ensureIO();
    var els = (root || document).querySelectorAll("[data-reveal]:not(.is-in)");
    if (!obs) { [].forEach.call(els, function (el) { el.classList.add("is-in"); }); return; }
    [].forEach.call(els, function (el, i) {
      if (el.style.getPropertyValue("--i") === "") el.style.setProperty("--i", (i % 8));
      obs.observe(el);
    });
  }

  // -------------------------------------------------------------- count up
  function countUp(el) {
    if (el._viCounted) return; el._viCounted = true;
    var target = parseFloat((el.dataset.countup != null ? el.dataset.countup : el.textContent).replace(/[, ]/g, ""));
    if (!isFinite(target)) return;
    var dur = 900, t0 = null, fmt = target >= 1000;
    if (reduce) { el.textContent = fmt ? target.toLocaleString() : String(target); return; }
    function step(ts) {
      if (t0 == null) t0 = ts;
      var p = Math.min((ts - t0) / dur, 1);
      var e = 1 - Math.pow(1 - p, 3); // easeOutCubic
      var v = Math.round(target * e);
      el.textContent = fmt ? v.toLocaleString() : String(v);
      if (p < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  }
  var countObs = null;
  function initCounts(root) {
    var els = (root || document).querySelectorAll("[data-countup]:not([data-cu])");
    if (!els.length) return;
    if (!("IntersectionObserver" in window)) { [].forEach.call(els, function (el) { el.setAttribute("data-cu", "1"); countUp(el); }); return; }
    if (!countObs) countObs = new IntersectionObserver(function (ents) {
      ents.forEach(function (en) { if (en.isIntersecting) { countUp(en.target); countObs.unobserve(en.target); } });
    }, { threshold: 0.4 });
    [].forEach.call(els, function (el) { el.setAttribute("data-cu", "1"); countObs.observe(el); }); // bound-once guard avoids leaking observers on re-scan
  }

  // -------------------------------------------------------------- spotlight
  function initSpotlight() {
    if (touch) return;
    var pending = null;
    document.addEventListener("pointermove", function (e) {
      pending = e;
      if (initSpotlight._raf) return;
      initSpotlight._raf = requestAnimationFrame(function () {
        initSpotlight._raf = 0;
        var ev = pending; if (!ev) return;
        var card = ev.target.closest && ev.target.closest(".vi-card");
        if (!card) return;
        var r = card.getBoundingClientRect();
        card.style.setProperty("--mx", (ev.clientX - r.left) + "px");
        card.style.setProperty("--my", (ev.clientY - r.top) + "px");
      });
    }, { passive: true });
  }

  // ----------------------------------------------------------------- ripple
  function initRipple() {
    if (reduce) return;
    document.addEventListener("pointerdown", function (e) {
      var t = e.target.closest && e.target.closest(".btn, .vi-chip, .kbtn, .vi-card, #vi-chat-send");
      if (!t) return;
      var r = t.getBoundingClientRect(), d = Math.max(r.width, r.height) * 2;
      var s = document.createElement("span");
      s.className = "vi-ripple";
      s.style.width = s.style.height = d + "px";
      s.style.left = (e.clientX - r.left) + "px";
      s.style.top = (e.clientY - r.top) + "px";
      t.appendChild(s);
      s.addEventListener("animationend", function () { s.remove(); });
    }, { passive: true });
  }

  // ------------------------------------------------------- magnetic launcher
  function initMagnetic(tries) {
    if (touch || reduce) return;
    tries = tries || 0;
    var el = document.getElementById("vi-chat-launcher");
    if (!el) { if (tries < 6) setTimeout(function () { initMagnetic(tries + 1); }, 600); return; } // launcher built by app.js; give up on pages without it
    var R = 90, pending = null, raf = 0;
    document.addEventListener("pointermove", function (e) {
      pending = e;
      if (raf) return;
      raf = requestAnimationFrame(function () {            // rAF-throttle: one rect read + style write per frame, not per event
        raf = 0; var ev = pending; if (!ev) return;
        var r = el.getBoundingClientRect();
        var dx = ev.clientX - (r.left + r.width / 2), dy = ev.clientY - (r.top + r.height / 2);
        if (Math.hypot(dx, dy) < R + 40 && !el.classList.contains("hidden")) {
          el.style.transform = "translate(" + dx * 0.28 + "px," + dy * 0.28 + "px)";
        } else if (el.style.transform) { el.style.transform = ""; }
      });
    }, { passive: true });
  }

  // catch [data-reveal]/[data-countup] injected after load (dashboard stats, lists)
  // so dynamic content reveals exactly like static — independent of inline rescan() timing
  function initMutationWatch() {
    if (!("MutationObserver" in window) || !document.body) return;
    var t = 0;
    new MutationObserver(function (muts) {
      var added = false;
      for (var i = 0; i < muts.length; i++) { if (muts[i].addedNodes && muts[i].addedNodes.length) { added = true; break; } }
      if (!added || t) return;
      t = setTimeout(function () { t = 0; try { observeReveals(document); initCounts(document); } catch (e) {} }, 80);
    }).observe(document.body, { childList: true, subtree: true });
  }

  // --------------------------------------------------------------- confetti
  VI.confetti = function (x, y) {
    if (reduce) return;
    var c = document.getElementById("vi-confetti");
    if (!c) { c = document.createElement("canvas"); c.id = "vi-confetti"; document.body.appendChild(c); }
    var ctx = c.getContext("2d"), W = c.width = innerWidth, H = c.height = innerHeight;
    x = x == null ? W / 2 : x; y = y == null ? H * 0.32 : y;
    var cols = ["#f59e0b", "#fcd34d", "#a3e635", "#fb7185", "#7c83ff", "#38bda0"];
    var P = [], N = 90;
    for (var i = 0; i < N; i++) {
      var a = Math.random() * Math.PI * 2, sp = 4 + Math.random() * 7;
      P.push({ x: x, y: y, vx: Math.cos(a) * sp, vy: Math.sin(a) * sp - 4,
        s: 4 + Math.random() * 5, col: cols[(Math.random() * cols.length) | 0],
        rot: Math.random() * 6.28, vr: (Math.random() - 0.5) * 0.4, life: 1 });
    }
    var t0 = null;
    function frame(ts) {
      if (t0 == null) t0 = ts;
      var dt = Math.min((ts - t0) / 16.7, 2); t0 = ts;
      ctx.clearRect(0, 0, W, H);
      var alive = false;
      for (var i = 0; i < P.length; i++) {
        var p = P[i]; if (p.life <= 0) continue; alive = true;
        p.vy += 0.22 * dt; p.x += p.vx * dt; p.y += p.vy * dt; p.rot += p.vr * dt; p.life -= 0.012 * dt;
        ctx.save(); ctx.globalAlpha = Math.max(p.life, 0); ctx.translate(p.x, p.y); ctx.rotate(p.rot);
        ctx.fillStyle = p.col; ctx.fillRect(-p.s / 2, -p.s / 2, p.s, p.s * 0.6); ctx.restore();
      }
      if (alive) requestAnimationFrame(frame);
      else { ctx.clearRect(0, 0, W, H); c.remove(); }
    }
    requestAnimationFrame(frame);
  };
  // fire confetti whenever a real achievement unlock toast is celebrated
  if (typeof VI.celebrate === "function" && !VI.celebrate._viWrapped) {
    var orig = VI.celebrate;
    VI.celebrate = function (keys) { try { if (keys && keys.length) VI.confetti(); } catch (e) {} return orig.apply(this, arguments); };
    VI.celebrate._viWrapped = true;
  }

  // ------------------------------------------------------------- public scan
  VI.motion = {
    scan: function (root) { try { observeReveals(root); initCounts(root); } catch (e) {} },
    reveal: revealAll,
    countUp: countUp,
    confetti: function (x, y) { VI.confetti(x, y); },
  };

  // ------------------------------------------------------------------- boot
  // Safety model (content must NEVER stay hidden), in order of defense:
  //   reduced-motion → CSS forces [data-reveal] visible + JS revealAll here
  //   IO missing      → observeReveals reveals immediately
  //   motion.js throws → catch → revealAll
  //   motion.js never loads → head-script 3s fallback (build.py) reveals all
  //   dynamic injects → MutationObserver re-observes (reveal on view, effect preserved)
  try {
    if (reduce) { revealAll(); initCounts(document); }
    else {
      observeReveals(document); initCounts(document);
      initSpotlight(); initRipple(); initMagnetic(); initMutationWatch();
      window.addEventListener("load", function () { try { observeReveals(document); initCounts(document); } catch (e) {} });
    }
  } catch (e) {
    revealAll(); // last-resort: never trap content
  }
})();
