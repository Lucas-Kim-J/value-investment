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
    palette.id = "vi-cmdk";
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
      (t.learned ? '<p style="font-size:12.5px;color:var(--accent);background:var(--accent-soft);padding:8px 10px;border-radius:8px;margin:0 0 10px">⚠️ 划词时 hermes 生成的草稿，涉及数字/事实请先去官方来源核对，再用自己的话标「掌握」。</p>' : "") +
      "<p>" + esc(t.definition || "") + "</p>" +
      (t.detail_url ? '<p><a href="' + t.detail_url + '">查看详细 →</a></p>' : "") +
      (rel ? '<p style="font-size:13px;color:var(--muted)">相关：' + rel + "</p>" : "") +
      '<hr style="border:none;border-top:1px solid var(--border);margin:16px 0">' +
      '<p style="font-size:13px;color:var(--muted)">用你自己的话讲一遍（讲得出才算掌握）：</p>' +
      '<textarea class="vi-ta" id="vi-restate" placeholder="我的复述…">' + esc(t.my_restatement || "") + "</textarea>" +
      '<div style="margin-top:10px;display:flex;gap:10px;align-items:center">' +
      '<button class="btn btn-primary btn-sm" id="vi-master">' + (t.mastery === "mastered" ? "已掌握 ✓ 更新" : "标记已掌握") + "</button>" +
      '<span class="status" id="vi-master-st"></span></div></div></div>';
    m.classList.add("open");
    // mark seen once (only if never recorded) — avoids downgrade + repeated recheck
    if (!t.mastery) VI.api("/api/terms/" + slug + "/mastery", { method: "PUT", body: { mastery: "seen" } });
    $("#vi-master").addEventListener("click", async () => {
      const v = $("#vi-restate").value.trim();
      const res = await VI.api("/api/terms/" + slug + "/mastery", { method: "PUT", body: { mastery: "mastered", restatement: v } });
      const st = $("#vi-master-st");
      if (res.ok) { st.textContent = "已掌握 ✓"; st.className = "status ok"; VI.celebrate(res.data.new_achievements); }
      else { st.textContent = res.data && res.data.error || "失败"; st.className = "status err"; }
    });
  }

  // ---- markdown render (shared) ----
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])); }
  function inl(s) { return esc(s).replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>").replace(/`([^`]+)`/g, "<code>$1</code>"); }
  VI.esc = esc;
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

  // ================= global hermes chat + selection-to-ask =================
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  let chatOpen = false, chatUser = null, chatLoaded = false, pendingCtx = "", pendingCtxLabel = "";
  const CHIPS = ["用我的水平解释一下", "这和我的持仓有什么关系", "出一道应用题考我"];

  function buildChat() {
    if ($("#vi-chat-launcher")) return;
    const l = document.createElement("button");
    l.id = "vi-chat-launcher"; l.title = "问 hermes (⌘J)"; l.innerHTML = "💬";
    l.addEventListener("click", VI.toggleChat);
    document.body.appendChild(l);
    const p = document.createElement("div");
    p.id = "vi-chat-panel";
    p.innerHTML =
      '<div class="vi-chat-head"><span>💬 hermes · 学习伙伴</span><button class="x" id="vi-chat-x">✕</button></div>' +
      '<div id="vi-chat-msgs" class="vi-chat-msgs"></div>' +
      '<div id="vi-chat-ctx" class="vi-chat-ctx" style="display:none"></div>' +
      '<div class="vi-chat-chips" id="vi-chat-chips"></div>' +
      '<div class="vi-chat-input"><textarea id="vi-chat-in" rows="1" placeholder="问 hermes 任何问题… (Enter 发送)"></textarea><button id="vi-chat-send">↑</button></div>';
    document.body.appendChild(p);
    $("#vi-chat-x").addEventListener("click", VI.toggleChat);
    $("#vi-chat-send").addEventListener("click", () => sendChat());
    const ta = $("#vi-chat-in");
    ta.addEventListener("keydown", e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendChat(); } });
    $("#vi-chat-chips").innerHTML = '<button class="vi-chip vi-chip-page" id="vi-chip-page">📄 看这一页</button>' + CHIPS.map(c => '<button class="vi-chip">' + c + "</button>").join("");
    $("#vi-chip-page").addEventListener("click", () => VI.askPage());
    [...$("#vi-chat-chips").querySelectorAll(".vi-chip:not(.vi-chip-page)")].forEach((b, i) => b.addEventListener("click", () => sendChat(CHIPS[i])));
  }
  function setCtx(text, label) {
    pendingCtx = text || ""; pendingCtxLabel = label || "";
    const el = $("#vi-chat-ctx"); if (!el) return;
    if (pendingCtx) { el.style.display = "flex"; el.innerHTML = '<span>📎 ' + esc(pendingCtxLabel || pendingCtx.slice(0, 50)) + '</span><button id="vi-ctx-x">✕</button>'; $("#vi-ctx-x").addEventListener("click", () => setCtx("")); }
    else { el.style.display = "none"; el.innerHTML = ""; }
  }
  function addMsg(role, html) {
    const m = $("#vi-chat-msgs");
    const div = document.createElement("div"); div.className = "vi-msg vi-msg-" + role; div.innerHTML = html;
    m.appendChild(div); m.scrollTop = m.scrollHeight; return div;
  }
  async function loadChatHistory() {
    if (!chatUser) { addMsg("bot", "👋 我是 hermes，你的学习伙伴。<a href='login.html'>登录</a>后就能问我问题——看文章时划词也能直接问我。"); return; }
    const r = await VI.api("/api/chat"); const items = (r.data && r.data.items) || [];
    if (!items.length) { addMsg("bot", "👋 我是 hermes。问我任何价值投资/方法论的问题；或在任意文章里划词 →「问 hermes」。我会按你的学习阶段回答。"); return; }
    items.forEach(t => { if (t.question) addMsg("user", esc(t.question)); if (t.reply) addMsg("bot", VI.renderMd(t.reply)); });
  }
  VI.toggleChat = async function () {
    buildChat(); chatOpen = !chatOpen;
    $("#vi-chat-panel").classList.toggle("open", chatOpen);
    $("#vi-chat-launcher").classList.toggle("hidden", chatOpen);
    if (chatOpen) { chatUser = await VI.me(); if (!chatLoaded) { await loadChatHistory(); chatLoaded = true; } setTimeout(() => { const i = $("#vi-chat-in"); if (i) i.focus(); }, 50); }
  };
  async function sendChat(text) {
    buildChat(); if (!chatOpen) await VI.toggleChat();
    chatUser = chatUser || await VI.me();
    if (!chatUser) { addMsg("bot", "请先 <a href='login.html'>登录</a> 再和我聊。"); return; }
    const q = (text != null ? text : $("#vi-chat-in").value).trim(); if (!q) return;
    const ctx = pendingCtx, ctxLabel = pendingCtxLabel;
    $("#vi-chat-in").value = ""; setCtx("");
    const tag = ctx ? '<span class="vi-ctx-tag">关于' + esc(ctxLabel || ("「" + ctx.slice(0, 50) + "」")) + "</span> " : "";
    addMsg("user", tag + esc(q));
    const thinking = addMsg("bot", '<span class="vi-think">思考中…</span>');
    const r = await VI.api("/api/chat", { body: { question: q, context: ctx } });
    if (r.status === 401) { thinking.innerHTML = "请先登录"; return; }
    if (!r.ok) { thinking.innerHTML = esc((r.data && r.data.error) || "出错了"); return; }
    const id = r.data.id; const t0 = Date.now();
    while (Date.now() - t0 < 240000) {
      await sleep(2500);
      let d; try { d = (await VI.api("/api/chat/" + id)).data; } catch (e) { continue; }
      if (!d) continue;
      if (d.status === "done") { thinking.innerHTML = VI.renderMd(d.reply); $("#vi-chat-msgs").scrollTop = 1e9; return; }
      if (d.status === "error") { thinking.innerHTML = '<span class="vi-think">' + esc(d.error || "出错") + "</span>"; return; }
      thinking.innerHTML = '<span class="vi-think">思考中… ' + Math.round((Date.now() - t0) / 1000) + "s</span>";
    }
    thinking.innerHTML = '<span class="vi-think">超时，请重试</span>';
  }
  VI.askAbout = async function (sel) {
    buildChat(); if (!chatOpen) await VI.toggleChat();
    setCtx(sel); const i = $("#vi-chat-in"); if (i) i.focus();
  };

  // page-aware: each page may expose VI.pageContext() returning a concise digest of
  // what's on screen + the user's state; otherwise we fall back to the visible text.
  function gatherPageContext() {
    try { if (typeof VI.pageContext === "function") { const s = VI.pageContext(); if (s) return String(s).slice(0, 2800); } } catch (e) {}
    const title = (document.querySelector(".app-head h1, h1") || {}).textContent || document.title || "";
    const main = document.querySelector(".app-wrap, main, body");
    const txt = main ? (main.innerText || "").replace(/\n{2,}/g, "\n").trim() : "";
    return ("【页面】" + title + "\n" + txt).slice(0, 2500);
  }
  VI.askPage = async function () {
    buildChat(); if (!chatOpen) await VI.toggleChat();
    const ctx = gatherPageContext();
    const name = ((document.querySelector(".app-head h1, h1") || {}).textContent || document.title || "本页").trim().slice(0, 16);
    setCtx(ctx, "本页：" + name);
    const i = $("#vi-chat-in");
    if (i) { if (!i.value.trim()) i.value = "结合这一页和我的水平，我该先读 / 先做哪个？给个顺序和理由"; i.focus(); }
  };

  // selection mini-toolbar
  function removeToolbar() { const t = $("#vi-sel-toolbar"); if (t) t.remove(); }
  function showToolbar(text, rect, ctx) {
    removeToolbar();
    const tb = document.createElement("div"); tb.id = "vi-sel-toolbar";
    tb.innerHTML = '<button data-a="explain">🔍 解释</button><button data-a="ask">💬 问 hermes</button>';
    document.body.appendChild(tb);
    // fixed (viewport) positioning so it also shows above scrollable / fixed modals
    const tw = tb.offsetWidth || 150, th = tb.offsetHeight || 34;
    let top = rect.bottom + 8, left = rect.left;
    if (top + th > window.innerHeight - 8) top = Math.max(8, rect.top - th - 8); // flip above if no room below
    left = Math.max(8, Math.min(left, window.innerWidth - tw - 8));              // clamp to viewport
    tb.style.top = top + "px"; tb.style.left = left + "px";
    tb.querySelector('[data-a="explain"]').addEventListener("click", () => { VI.explain(text, ctx); removeToolbar(); });
    tb.querySelector('[data-a="ask"]').addEventListener("click", () => { VI.askAbout(text); removeToolbar(); });
  }

  // inline 解释 card: hermes explains the selection (grounded on the curated term if any),
  // then offers to save unknown terms into the wiki ("我划词学的").
  VI.explain = async function (text, context) {
    let m = $("#vi-explain-modal");
    if (!m) {
      m = document.createElement("div"); m.id = "vi-explain-modal"; m.className = "vi-modal-bg";
      document.body.appendChild(m); m.addEventListener("click", e => { if (e.target === m) m.classList.remove("open"); });
    }
    m.innerHTML =
      '<div class="vi-modal" style="max-width:520px"><div class="vi-modal-head">' +
      '<h2>🔍 ' + esc(text.slice(0, 40)) + (text.length > 40 ? "…" : "") + '</h2>' +
      '<button class="x" id="vi-ex-x">✕</button></div>' +
      '<div class="vi-modal-body" id="vi-ex-body"><p class="vi-think">解释中…</p></div></div>';
    m.classList.add("open");
    $("#vi-ex-x").addEventListener("click", () => m.classList.remove("open"));
    const body = $("#vi-ex-body");
    let r;
    try { r = await VI.api("/api/explain", { body: { text, context: context || "" } }); }
    catch (e) { body.innerHTML = '<p class="status err">请求失败，请重试</p>'; return; }
    if (r.status === 401) { body.innerHTML = "请先 <a href='login.html'>登录</a> 再用解释功能。"; return; }
    if (!r.ok) { body.innerHTML = '<p class="status err">' + esc((r.data && r.data.error) || "出错了") + "</p>"; return; }
    const curated = r.data.curated, jid = r.data.id;
    let head = "";
    if (curated) {
      head = '<div class="vi-ex-curated"><div class="vi-ex-label"><span class="cov cov-guide">术语库</span> ' +
        esc(curated.term) + (curated.term_en ? ' <span class="en">' + esc(curated.term_en) + "</span>" : "") + "</div>" +
        "<p>" + esc(curated.definition || "") + "</p>" +
        '<a href="#" id="vi-ex-card">查看完整术语卡 →</a></div>';
    }
    body.innerHTML = head +
      '<div class="vi-ex-hermes"><div class="vi-ex-label">💬 hermes 讲解' +
      (curated ? "" : ' <span class="vi-ex-draft">未收录术语 · AI 草稿</span>') + "</div>" +
      '<div id="vi-ex-reply"><span class="vi-think">解释中… 0s</span></div></div>' +
      '<div id="vi-ex-actions" class="vi-ex-actions"></div>';
    if (curated) $("#vi-ex-card").addEventListener("click", e => { e.preventDefault(); m.classList.remove("open"); VI.showTerm(curated.slug); });
    // poll for the explanation
    const reply = $("#vi-ex-reply"); const t0 = Date.now(); let finalReply = "";
    while (Date.now() - t0 < 240000) {
      await sleep(2500);
      if (!document.body.contains(reply)) return; // card closed/replaced
      let d; try { d = (await VI.api("/api/explain/" + jid)).data; } catch (e) { continue; }
      if (!d) continue;
      if (d.status === "done") { finalReply = d.reply || ""; reply.innerHTML = VI.renderMd(finalReply); break; }
      if (d.status === "error") { reply.innerHTML = '<span class="vi-think">' + esc(d.error || "出错") + "</span>"; break; }
      reply.innerHTML = '<span class="vi-think">解释中… ' + Math.round((Date.now() - t0) / 1000) + "s</span>";
    }
    const actions = $("#vi-ex-actions"); if (!actions) return;
    let btns = '<button class="btn btn-ghost btn-sm" id="vi-ex-ask">💬 在聊天里追问</button>';
    if (!curated && finalReply) btns = '<button class="btn btn-primary btn-sm" id="vi-ex-save">📌 收入术语库</button> ' + btns;
    actions.innerHTML = btns;
    if ($("#vi-ex-ask")) $("#vi-ex-ask").addEventListener("click", () => { m.classList.remove("open"); VI.askAbout(text); });
    if ($("#vi-ex-save")) $("#vi-ex-save").addEventListener("click", async () => {
      const b = $("#vi-ex-save"); b.disabled = true; b.textContent = "收入中…";
      const res = await VI.api("/api/terms/learned", { body: { term: text, definition: finalReply, context: context || "" } });
      if (res.ok) { b.textContent = "已收入 ✓"; VI.toast("已收入「我划词学的」——可去术语 Wiki 复习 / 标掌握", "📌"); VI.celebrate(res.data.new_achievements); }
      else { b.disabled = false; b.textContent = "📌 收入术语库"; VI.toast((res.data && res.data.error) || "收藏失败"); }
    });
  };

  function initSelection() {
    document.addEventListener("mouseup", e => {
      // skip the chat panel, ⌘K palette and interactive controls — but allow content modals (canon/term)
      if (e.target.closest("#vi-chat-panel, #vi-cmdk, input, textarea, #vi-sel-toolbar, button, a")) return;
      setTimeout(() => {
        const sel = window.getSelection(); const text = (sel ? sel.toString() : "").trim();
        removeToolbar();
        if (text.length < 2 || text.length > 120 || !sel.rangeCount) return;
        const range = sel.getRangeAt(0);
        // capture the surrounding sentence/block as context for a better explanation
        const node = range.startContainer; const blk = node.nodeType === 3 ? node.parentElement : node;
        const ctx = (blk ? (blk.textContent || "") : "").trim().slice(0, 300);
        showToolbar(text, range.getBoundingClientRect(), ctx);
      }, 10);
    });
    document.addEventListener("mousedown", e => { if (!e.target.closest("#vi-sel-toolbar")) removeToolbar(); });
    // fixed toolbar would float away from the selection on scroll → dismiss it (catches modal-body scroll too)
    window.addEventListener("scroll", removeToolbar, true);
  }

  // ---- global hotkeys + init ----
  document.addEventListener("keydown", (e) => {
    if ((e.metaKey || e.ctrlKey) && (e.key === "k" || e.key === "K")) { e.preventDefault(); VI.openCmdk(); }
    if ((e.metaKey || e.ctrlKey) && (e.key === "j" || e.key === "J")) { e.preventDefault(); VI.toggleChat(); }
  });
  buildChat();
  initSelection();
})();
