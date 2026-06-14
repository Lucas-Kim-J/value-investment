import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { apiGet, apiPut } from "../lib/api";
import type { TermDetail } from "../lib/types";

export function TermModal({
  slug,
  onClose,
  onPick,
  onCelebrate,
}: {
  slug: string;
  onClose: () => void;
  onPick: (s: string) => void;
  onCelebrate: (keys?: string[]) => void;
}) {
  const [t, setT] = useState<TermDetail | null>(null);
  const [restate, setRestate] = useState("");
  const [st, setSt] = useState<{ msg: string; cls: string }>({ msg: "", cls: "" });

  useEffect(() => {
    let alive = true;
    apiGet<TermDetail>("/api/terms/" + slug).then((r) => {
      if (!alive) return;
      const d = r.data;
      if (!d || d.error) {
        onClose();
        return;
      }
      setT(d);
      setRestate(d.my_restatement || "");
      if (!d.mastery) apiPut("/api/terms/" + slug + "/mastery", { mastery: "seen" });
    });
    return () => {
      alive = false;
    };
    // intentionally only on slug: re-running on onClose identity would refetch + re-fire mark-seen
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [slug]);

  async function mark() {
    const v = restate.trim();
    const r = await apiPut<{ ok: boolean; error?: string; new_achievements?: string[] }>(
      "/api/terms/" + slug + "/mastery",
      { mastery: "mastered", restatement: v },
    );
    if (r.ok) {
      setSt({ msg: "已掌握 ✓", cls: "ok" });
      onCelebrate(r.data?.new_achievements);
    } else {
      setSt({ msg: r.data?.error || "失败", cls: "err" });
    }
  }

  if (!t) return null;
  return (
    <motion.div
      className="vi-modal-bg"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <motion.div
        className="vi-modal"
        initial={{ opacity: 0, y: 12, scale: 0.97 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        exit={{ opacity: 0, y: 12, scale: 0.97 }}
        transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
      >
        <div className="vi-modal-head">
          <h2>
            {t.term} {t.term_en && <span style={{ color: "var(--muted)", fontSize: 14, fontWeight: 400 }}>{t.term_en}</span>}
          </h2>
          <button className="x" onClick={onClose}>✕</button>
        </div>
        <div className="vi-modal-body">
          {t.learned && (
            <p style={{ fontSize: 12.5, color: "var(--accent)", background: "var(--accent-soft)", padding: "8px 10px", borderRadius: 8, margin: "0 0 10px" }}>
              ⚠️ 划词时 hermes 生成的草稿，涉及数字/事实请先去官方来源核对，再用自己的话标「掌握」。
            </p>
          )}
          <p>{t.definition}</p>
          {t.detail_url && (
            <p>
              <a href={t.detail_url}>查看详细 →</a>
            </p>
          )}
          {t.related && t.related.length > 0 && (
            <p style={{ fontSize: 13, color: "var(--muted)" }}>
              相关：
              {t.related.map((s, i) => (
                <span key={s}>
                  {i > 0 && "　"}
                  <a href="#" onClick={(e) => { e.preventDefault(); onPick(s); }}>{s}</a>
                </span>
              ))}
            </p>
          )}
          {t.appears_in && t.appears_in.length > 0 && (
            <p style={{ fontSize: 13, color: "var(--muted)" }}>
              📚 出现在你的一手内容：{t.appears_in.map((c) => "《" + c.title + "》").join("、")}
            </p>
          )}
          <hr style={{ border: "none", borderTop: "1px solid var(--border)", margin: "16px 0" }} />
          <p style={{ fontSize: 13, color: "var(--muted)" }}>用你自己的话讲一遍（讲得出才算掌握）：</p>
          <textarea className="vi-ta" value={restate} onChange={(e) => setRestate(e.target.value)} placeholder="我的复述…" style={{ width: "100%", minHeight: 80 }} />
          <div style={{ marginTop: 10, display: "flex", gap: 10, alignItems: "center" }}>
            <button className="btn btn-primary btn-sm" onClick={mark}>{t.mastery === "mastered" ? "已掌握 ✓ 更新" : "标记已掌握"}</button>
            <span className={"status " + st.cls}>{st.msg}</span>
          </div>
        </div>
      </motion.div>
    </motion.div>
  );
}
