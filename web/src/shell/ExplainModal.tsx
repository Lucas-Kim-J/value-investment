import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { apiGet, apiPost } from "../lib/api";
import type { AsyncJob, CuratedTerm, ExplainResp } from "../lib/types";
import { Markdown } from "./Markdown";

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

/** Inline 解释 card: hermes explains a selection (grounded on the curated term if any),
 *  then offers to save an unknown term into the wiki ("我划词学的"). */
export function ExplainModal({
  text, context, onClose, toast, celebrate, openTerm, askAbout,
}: {
  text: string;
  context: string;
  onClose: () => void;
  toast: (msg: string, ico?: string) => void;
  celebrate: (keys?: string[]) => void;
  openTerm: (slug: string) => void;
  askAbout: (text: string) => void;
}) {
  const [curated, setCurated] = useState<CuratedTerm | null>(null);
  const [reply, setReply] = useState("");
  const [status, setStatus] = useState<"thinking" | "done" | "error">("thinking");
  const [elapsed, setElapsed] = useState(0);
  const [err, setErr] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    (async () => {
      let r;
      try {
        r = await apiPost<ExplainResp>("/api/explain", { text, context: context || "" });
      } catch {
        if (mounted.current) setErr("请求失败，请重试");
        return;
      }
      if (!mounted.current) return;
      if (r.status === 401) { setErr("login"); return; }
      if (!r.ok || !r.data?.id) { setErr(r.data?.error || "出错了"); return; }
      setCurated(r.data.curated ?? null);
      const id = r.data.id;
      const t0 = Date.now();
      while (mounted.current && Date.now() - t0 < 240000) {
        await sleep(2500);
        if (!mounted.current) return;
        let d: AsyncJob | null = null;
        try { d = (await apiGet<AsyncJob>("/api/explain/" + id)).data; } catch { continue; }
        if (!d) continue;
        if (d.status === "done") { setReply(d.reply || ""); setStatus("done"); return; }
        if (d.status === "error") { setReply(d.error || "出错"); setStatus("error"); return; }
        setElapsed(Math.round((Date.now() - t0) / 1000));
      }
      if (mounted.current) { setReply("超时，请重试"); setStatus("error"); }
    })();
    return () => { mounted.current = false; };
  }, [text, context]);

  async function save() {
    setSaving(true);
    const res = await apiPost<{ new_achievements?: string[]; error?: string }>("/api/terms/learned", { term: text, definition: reply, context: context || "" });
    if (res.ok) {
      setSaved(true);
      toast("已收入「我划词学的」——可去术语 Wiki 复习 / 标掌握", "📌");
      celebrate(res.data?.new_achievements);
    } else {
      setSaving(false);
      toast(res.data?.error || "收藏失败");
    }
  }

  return (
    <motion.div
      className="vi-modal-bg"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
      initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.16 }}
    >
      <motion.div
        className="vi-modal" style={{ maxWidth: 520 }}
        initial={{ opacity: 0, y: 14, scale: 0.98 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: 8, scale: 0.98 }}
        transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
      >
        <div className="vi-modal-head">
          <h2>🔍 {text.slice(0, 40)}{text.length > 40 ? "…" : ""}</h2>
          <button className="x" onClick={onClose}>✕</button>
        </div>
        <div className="vi-modal-body">
          {err === "login" ? (
            <p>请先 <a href="/login">登录</a> 再用解释功能。</p>
          ) : err ? (
            <p className="status err">{err}</p>
          ) : (
            <>
              {curated && (
                <div className="vi-ex-curated">
                  <div className="vi-ex-label">
                    <span className="cov cov-guide">术语库</span> {curated.term}
                    {curated.term_en && <>{" "}<span className="en">{curated.term_en}</span></>}
                  </div>
                  <p>{curated.definition || ""}</p>
                  <a href="#" onClick={(e) => { e.preventDefault(); onClose(); openTerm(curated.slug); }}>查看完整术语卡 →</a>
                </div>
              )}
              <div className="vi-ex-hermes">
                <div className="vi-ex-label">
                  💬 hermes 讲解
                  {!curated && <span className="vi-ex-draft">未收录术语 · AI 草稿</span>}
                </div>
                <div>
                  {status === "done" ? (
                    <Markdown className="md-render vi-ex-reply">{reply}</Markdown>
                  ) : (
                    <span className="vi-think">{status === "error" ? reply : "解释中… " + elapsed + "s"}</span>
                  )}
                </div>
              </div>
              <div className="vi-ex-actions">
                {!curated && status === "done" && reply && (
                  <button className="btn btn-primary btn-sm" disabled={saving || saved} onClick={save}>
                    {saved ? "已收入 ✓" : saving ? "收入中…" : "📌 收入术语库"}
                  </button>
                )}
                <button className="btn btn-ghost btn-sm" onClick={() => { onClose(); askAbout(text); }}>💬 在聊天里追问</button>
              </div>
            </>
          )}
        </div>
      </motion.div>
    </motion.div>
  );
}
