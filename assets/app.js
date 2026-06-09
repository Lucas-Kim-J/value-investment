/* Shared app shell for v2 pages: nav, global ⌘K term search, markdown render,
   auth helper, toast + achievement-unlock notifications. Vanilla JS. */
(function () {
  const VI = (window.VI = window.VI || {});
  const $ = (s, r = document) => r.querySelector(s);

  // ---- API helper ----
  VI.api = async function (path, opts) {
    opts = opts || {};
    const o = { credentials: "same-origin", headers: {} };
    if (opts.body !== undefined) { o.method = opts.method || "POST"; o.headers["Content-Type"] = "application/json"; o.body = JSON.stringify(opts.body); }
    else if (opts.method) o.method = opts.method;
    const r = await fetch(path, o);
    let d = null; try { d = await r.json(); } catch (e) {}
    return { ok: r.ok, status: r.status, data: d };
  };

  VI.me = async function () { const r = await VI.api("/api/me"); return r.data && r.data.user; };
  VI.requireAuth = async function () { const u = await VI.me(); if (!u) location.replace("login.html"); return u; };

  // ---- toast + achievements ----
  VI.toast = function (msg, ico) {
    let t = $(".toast"); if (!t) { t = document.createElement("div"); t.className = "toast"; document.body.appendChild(t); }
    t.innerHTML = (ico ? '<span class="ico">' + ico + "</span>" : "") + msg;
    t.classList.add("show"); clearTimeout(t._h); t._h = setTimeout(() => t.classList.remove("show"), 3200);
  };
  VI.celebrate = function (keys) {
    if (!keys || !keys.length) return;
    const titles = (VI._achTitles || {});
    keys.forEach((k, i) => setTimeout(() => VI.toast("解锁成就：" + (titles[k] || k), "🏅"), i * 900));
  };
  VI.loadAchTitles = async function () {
    const r = await VI.api("/api/achievements"); if (r.data && r.data.items) { VI._achTitles = {}; r.data.items.forEach(a => VI._achTitles[a.key] = a.title); }
  };

  // ---- nav ----
  const NAV = [
    ["dashboard.html", "🏠 首页", "home"],
    ["learn.html", "📖 学习", "learn"],
    ["canon.html", "📚 一手内容", "canon"],
    ["wiki.html", "🔍 术语", "wiki"],
    ["portfolio.html", "💼 我的持仓", "portfolio"],
    ["analyze.html", "🏢 公司分析", "analyze"],
    ["achievements.html", "🏅 成就", "achievements"],
  ];
  VI.nav = function (active, user) {
    const el = $("#vi-nav"); if (!el) return;
    el.className = "vi-nav";
    el.innerHTML =
      NAV.map(([h, label, key]) => `<a href="${h}" class="${key === active ? "active" : ""}">${label}</a>`).join("") +
      `<span class="sp"></span>` +
      `<span class="kbtn" id="vi-cmdk-btn">🔍 术语速查 <kbd>⌘K</kbd></span>` +
      (user ? `<span class="who">👤 <b>${user}</b></span>` : "");
    $("#vi-cmdk-btn").addEventListener("click", VI.openCmdk);
  };

  // ---- ⌘K term palette ----
  let TERMS = null, palette = null, sel = 0, filtered = [];
  async function ensureTerms() {
    if (TERMS) return TERMS;
    try { const r = await fetch("/assets/terms.json"); TERMS = await r.json(); } catch (e) { TERMS = []; }
    return TERMS;
  }
  function buildPalette() {
    palette = document.createElement("div");
    palette.className = "vi-modal-bg";
    palette.innerHTML =
      '<div class="vi-modal" style="max-width:560px">' +
      '<input class="cmdk-input" id="cmdk-in" placeholder="搜术语… (中文 / English)" autocomplete="off">' +
      '<div class="cmdk-results" id="cmdk-res"></div></div>';
    document.body.appendChild(palette);
    palette.addEventListener("click", (e) => { if (e.target === palette) closeCmdk(); });
    $("#cmdk-in").addEventListener("input", renderCmdk);
    $("#cmdk-in").addEventListener("keydown", (e) => {
      if (e.key === "ArrowDown") { sel = Math.min(sel + 1, filtered.length - 1); paintSel(); e.preventDefault(); }
      else if (e.key === "ArrowUp") { sel = Math.max(sel - 1, 0); paintSel(); e.preventDefault(); }
      else if (e.key === "Enter" && filtered[sel]) { showTerm(filtered[sel].slug); }
      else if (e.key === "Escape") closeCmdk();
    });
  }
  function paintSel() { [...document.querySelectorAll(".cmdk-item")].forEach((el, i) => el.classList.toggle("sel", i === sel)); }
  function renderCmdk() {
    const q = ($("#cmdk-in").value || "").trim().toLowerCase();
    filtered = !q ? TERMS.slice(0, 8) : TERMS.filter(t =>
      (t.term || "").toLowerCase().includes(q) || (t.en || "").toLowerCase().includes(q) || (t.slug || "").includes(q)).slice(0, 20);
    sel = 0;
    const res = $("#cmdk-res");
    if (!filtered.length) { res.innerHTML = '<div class="cmdk-empty">没有匹配的术语。试试英文，或去 <a href="wiki.html">术语 Wiki</a> 浏览。</div>'; return; }
    res.innerHTML = filtered.map((t, i) =>
      `<div class="cmdk-item ${i === 0 ? "sel" : ""}" data-slug="${t.slug}">
        <div class="t">${t.term}${t.en ? '<span class="en">' + t.en + "</span>" : ""}</div>
        <div class="d">${(t.definition || "").slice(0, 90)}</div>
        ${t.category ? '<div class="cat">' + t.category + "</div>" : ""}
      </div>`).join("");
    [...res.querySelectorAll(".cmdk-item")].forEach(el => el.addEventListener("click", () => showTerm(el.dataset.slug)));
  }
  VI.openCmdk = async function () {
    await ensureTerms(); if (!palette) buildPalette();
    palette.classList.add("open"); renderCmdk(); setTimeout(() => $("#cmdk-in").focus(), 30);
  };
  function closeCmdk() { if (palette) palette.classList.remove("open"); }
  VI.closeCmdk = closeCmdk;

  // term detail (used by ⌘K and wiki); opens a modal with definition + actions
  VI.showTerm = showTerm;
  async function showTerm(slug) {
    closeCmdk();
    const r = await VI.api("/api/terms/" + slug);
    const t = r.data; if (!t || t.error) return;
    let m = $("#vi-term-modal");
    if (!m) { m = document.createElement("div"); m.id = "vi-term-modal"; m.className = "vi-modal-bg"; document.body.appendChild(m); m.addEventListener("click", e => { if (e.target === m) m.classList.remove("open"); }); }
    const rel = (t.related || []).map(s => `<a href="#" onclick="VI.showTerm('${s}');return false">${s}</a>`).join("　");
    m.innerHTML =
      '<div class="vi-modal"><div class="vi-modal-head"><h2>' + t.term + (t.term_en ? ' <span style="color:var(--muted);font-size:14px;font-weight:400">' + t.term_en + "</span>" : "") +
      '</h2><button class="x" onclick="document.getElementById(\'vi-term-modal\').classList.remove(\'open\')">✕</button></div>' +
      '<div class="vi-modal-body">' +
      "<p>" + (t.definition || "") + "</p>" +
      (t.detail_url ? '<p><a href="' + t.detail_url + '">查看详细 →</a></p>' : "") +
      (rel ? '<p style="font-size:13px;color:var(--muted)">相关：' + rel + "</p>" : "") +
      '<hr style="border:none;border-top:1px solid var(--border);margin:16px 0">' +
      '<p style="font-size:13px;color:var(--muted)">用你自己的话讲一遍（讲得出才算掌握）：</p>' +
      '<textarea class="vi-ta" id="vi-restate" placeholder="我的复述…">' + (t.my_restatement || "") + "</textarea>" +
      '<div style="margin-top:10px;display:flex;gap:10px;align-items:center">' +
      '<button class="btn btn-primary btn-sm" id="vi-master">' + (t.mastery === "mastered" ? "已掌握 ✓ 更新" : "标记已掌握") + "</button>" +
      '<span class="status" id="vi-master-st"></span></div></div></div>";
    m.classList.add("open");
    // mark seen (best-effort, only if logged in)
    VI.api("/api/terms/" + slug + "/mastery", { method: "PUT", body: { mastery: t.mastery === "mastered" ? "mastered" : "seen", restatement: t.my_restatement || "" } });
    $("#vi-master").addEventListener("click", async () => {
      const v = $("#vi-restate").value.trim();
      const res = await VI.api("/api/terms/" + slug + "/mastery", { method: "PUT", body: { mastery: "mastered", restatement: v } });
      const st = $("#vi-master-st");
      if (res.ok) { st.textContent = "已掌握 ✓"; st.className = "status ok"; VI.celebrate(res.data.new_achievements); }
      else { st.textContent = res.data && res.data.error || "失败"; st.className = "status err"; }
    });
  }

  // ---- markdown render (shared) ----
  function esc(s) { return String(s).replace(/[&<>]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c])); }
  function inl(s) { return esc(s).replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>").replace(/`([^`]+)`/g, "<code>$1</code>"); }
  VI.renderMd = function (md) {
    const lines = String(md || "").replace(/\r/g, "").split("\n"); const out = []; let i = 0;
    const isB = l => /^#{1,6}\s|^\s*[-*]\s|^\s*\d+\.\s|^\s*---+\s*$/.test(l);
    while (i < lines.length) {
      const l = lines[i]; if (/^\s*$/.test(l)) { i++; continue; } let m;
      if (m = l.match(/^(#{1,6})\s+(.*)/)) { const n = Math.min(m[1].length, 4); out.push(`<h${n}>${inl(m[2])}</h${n}>`); i++; continue; }
      if (/^\s*---+\s*$/.test(l)) { out.push("<hr>"); i++; continue; }
      if (/^\s*[-*]\s+/.test(l)) { const it = []; while (i < lines.length && /^\s*[-*]\s+/.test(lines[i])) { it.push("<li>" + inl(lines[i].replace(/^\s*[-*]\s+/, "")) + "</li>"); i++; } out.push("<ul>" + it.join("") + "</ul>"); continue; }
      if (/^\s*\d+\.\s+/.test(l)) { const it = []; while (i < lines.length && /^\s*\d+\.\s+/.test(lines[i])) { it.push("<li>" + inl(lines[i].replace(/^\s*\d+\.\s+/, "")) + "</li>"); i++; } out.push("<ol>" + it.join("") + "</ol>"); continue; }
      const p = []; while (i < lines.length && !/^\s*$/.test(lines[i]) && !isB(lines[i])) { p.push(inl(lines[i])); i++; } out.push("<p>" + p.join("<br>") + "</p>");
    }
    return out.join("\n");
  };

  // ---- global ⌘K hotkey ----
  document.addEventListener("keydown", (e) => {
    if ((e.metaKey || e.ctrlKey) && (e.key === "k" || e.key === "K")) { e.preventDefault(); VI.openCmdk(); }
  });
})();
