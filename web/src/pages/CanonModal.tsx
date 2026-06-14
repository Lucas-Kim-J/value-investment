import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { apiGet, apiPost, apiPut } from "../lib/api";
import type { CanonDetail, Holding } from "../lib/types";

const KINDS: Record<string, string> = { letter: "Letter 信", agm: "AGM 股东会", "13f": "13F 持仓", quarterly: "季报/10-K", talk: "演讲/访谈", book: "书", memo: "备忘录", tool: "工具源" };
const TIERS: Record<string, string> = { tier0: "起点必读", tier1: "核心", tier2: "拓展" };
const ZLIB = "https://z-lib.io/s/";

export function CanonModal({
  slug, user, holdings, onClose, onPick, onCelebrate, onRead,
}: {
  slug: string;
  user: string | null;
  holdings: Holding[];
  onClose: () => void;
  onPick: (s: string) => void;
  onCelebrate: (keys?: string[]) => void;
  onRead: (slug: string) => void;
}) {
  const [it, setIt] = useState<CanonDetail | null>(null);
  const [note, setNote] = useState("");
  const [st, setSt] = useState<{ msg: string; cls: string }>({ msg: "", cls: "" });
  const [readNext, setReadNext] = useState<string[] | null>(null);
  const [thesisTk, setThesisTk] = useState("");
  const [thesisBusy, setThesisBusy] = useState(false);
  const [thesisSt, setThesisSt] = useState<{ msg: string; cls: string }>({ msg: "", cls: "" });

  useEffect(() => {
    let alive = true;
    apiGet<CanonDetail>("/api/canon/" + slug).then((r) => {
      if (!alive) return;
      const d = r.data;
      if (!d || d.error) {
        onClose();
        return;
      }
      setIt(d);
      const last = (d.my_events || []).filter((e) => e.detail?.note).slice(-1)[0];
      setNote(last?.detail?.note || "");
    });
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [slug]);

  useEffect(() => {
    if (holdings[0]) setThesisTk(holdings[0].ticker);
  }, [holdings]);

  async function mark() {
    if (!user) {
      window.location.href = "/login";
      return;
    }
    const r = await apiPost<{ ok: boolean; error?: string; new_achievements?: string[] }>("/api/canon/" + slug + "/read", { note: note.trim(), minutes: 30 });
    if (r.ok) {
      setSt({ msg: note.trim() ? "已记下 ✓" : "已标为已读 ✓", cls: "ok" });
      onCelebrate(r.data?.new_achievements);
      onRead(slug);
      if (it?.related_terms?.length) setReadNext(it.related_terms);
    } else {
      setSt({ msg: r.data?.error || "失败", cls: "err" });
    }
  }

  async function attachThesis() {
    const n = note.trim();
    if (!n) {
      setThesisSt({ msg: "先在上面写一句收获", cls: "err" });
      return;
    }
    setThesisBusy(true);
    setThesisSt({ msg: "挂上中…", cls: "" });
    try {
      const cur = (await apiGet<{ holdings: Holding[] }>("/api/holdings")).data?.holdings || [];
      // normalize buy_date (null round-trips to a "None" string on the server) and append the note
      const out = cur.map((x) => ({ ...x, buy_date: x.buy_date || "" }));
      const h = out.find((x) => x.ticker === thesisTk);
      if (h) h.note = (h.note ? h.note + " / " : "") + `[${it?.title}] ${n}`;
      const rr = await apiPut<{ ok: boolean; error?: string }>("/api/holdings", { holdings: out });
      if (rr.ok) setThesisSt({ msg: "已挂到 " + thesisTk + " 的 thesis ✓", cls: "ok" });
      else {
        setThesisBusy(false);
        setThesisSt({ msg: rr.data?.error || "失败", cls: "err" });
      }
    } catch {
      setThesisBusy(false);
      setThesisSt({ msg: "网络错误", cls: "err" });
    }
  }

  if (!it) return null;
  const zlibQ = encodeURIComponent((it.title || "").split("（")[0].split("(")[0].trim());

  return (
    <motion.div className="vi-modal-bg" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <motion.div className="vi-modal" initial={{ opacity: 0, y: 12, scale: 0.97 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: 12, scale: 0.97 }} transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}>
        <div className="vi-modal-head"><h2>{it.title}</h2><button className="x" onClick={onClose}>✕</button></div>
        <div className="vi-modal-body">
          <p style={{ color: "var(--muted)", fontSize: 13 }}>
            <span className="kind-tag">{KINDS[it.kind] || it.kind}</span> {it.source} · {it.period} · {TIERS[it.tier] || it.tier} · 约 {Math.round((it.est_minutes || 0) / 60)} 小时
          </p>
          <p><strong>为什么读：</strong>{it.why}</p>
          <p><strong>导读：</strong>{it.guide}</p>
          {it.questions && it.questions.length > 0 && (
            <>
              <p><strong>读完应能回答：</strong></p>
              <ul style={{ color: "var(--fg-soft)", paddingLeft: 20 }}>{it.questions.map((q, i) => <li key={i}>{q}</li>)}</ul>
            </>
          )}
          {it.official_url ? (
            <p><a href={it.official_url} target="_blank" rel="noopener">📎 官方原文 / 权威链接 →</a></p>
          ) : (
            <p style={{ color: "var(--muted)", fontSize: 13 }}>官方链接待核实——请自行搜索权威来源。</p>
          )}
          {it.kind === "book" && (
            <p><a href={ZLIB + zlibQ} target="_blank" rel="noopener">📚 在 Z-Library 找这本书读 →</a></p>
          )}
          {it.related_terms && it.related_terms.length > 0 && (
            <p style={{ fontSize: 13, color: "var(--muted)" }}>
              相关术语：{it.related_terms.map((s, i) => <span key={s}>{i > 0 && "　"}<a href="#" onClick={(e) => { e.preventDefault(); onPick(s); }}>{s}</a></span>)}
            </p>
          )}
          <hr style={{ border: "none", borderTop: "1px solid var(--border)", margin: "16px 0" }} />
          <p style={{ fontSize: 13, color: "var(--muted)" }}>读完写一句你的收获（不是摘抄，是你自己的话）→ 留痕 + 可能解锁成就：</p>
          <textarea className="vi-ta" value={note} onChange={(e) => setNote(e.target.value)} placeholder="我的收获 / 关联到我的某笔持仓…" style={{ width: "100%", minHeight: 80 }} />
          <div style={{ marginTop: 10, display: "flex", gap: 10, alignItems: "center" }}>
            <button className="btn btn-primary btn-sm" onClick={mark}>{user ? "记下 + 标为已读" : "登录后可留痕"}</button>
            <span className={"status " + st.cls}>{st.msg}</span>
          </div>
          {readNext && (
            <div className="handoff">
              👉 下一步：这篇关联 {readNext.length} 个术语，去把它们打底 → {readNext.map((s, i) => <span key={s}>{i > 0 && "　"}<a href="#" onClick={(e) => { e.preventDefault(); onPick(s); }}>{s}</a></span>)}
            </div>
          )}
          {user && holdings.length > 0 && (
            <div className="handoff" style={{ background: "var(--accent-soft)", borderLeftColor: "var(--accent)", marginTop: 10 }}>
              📌 把这条收获挂到某个持仓的 thesis：
              <select className="vi-in" value={thesisTk} onChange={(e) => setThesisTk(e.target.value)} style={{ padding: "5px 8px", margin: "0 4px" }}>
                {holdings.map((h) => <option key={h.ticker} value={h.ticker}>{h.ticker}{h.name ? " " + h.name : ""}</option>)}
              </select>
              <button className="btn btn-ghost btn-sm" onClick={attachThesis} disabled={thesisBusy}>挂上</button> <span className={"status " + thesisSt.cls}>{thesisSt.msg}</span>
            </div>
          )}
        </div>
      </motion.div>
    </motion.div>
  );
}
