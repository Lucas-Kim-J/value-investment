import { useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import { apiGet } from "../lib/api";
import { useShell } from "../shell/ShellContext";
import type { GlossaryTerm } from "../lib/types";

export default function Wiki() {
  const { openTerm } = useShell();
  const [all, setAll] = useState<GlossaryTerm[]>([]);
  const [q, setQ] = useState("");

  useEffect(() => {
    apiGet<{ items: GlossaryTerm[] }>("/api/terms").then((r) => setAll(r.data?.items ?? []));
  }, []);

  const filtered = useMemo(() => {
    const s = q.trim().toLowerCase();
    if (!s) return all;
    return all.filter(
      (t) => (t.term || "").toLowerCase().includes(s) || (t.term_en || "").toLowerCase().includes(s) || (t.slug || "").includes(s),
    );
  }, [q, all]);

  const byCat = useMemo(() => {
    const m: Record<string, GlossaryTerm[]> = {};
    for (const t of filtered) (m[t.category || "其他"] ||= []).push(t);
    return m;
  }, [filtered]);

  const masteredN = all.filter((t) => t.mastery === "mastered").length;

  return (
    <>
      <div className="app-head">
        <div className="eyebrow">Glossary Wiki</div>
        <h1>术语 Wiki</h1>
        <p>
          价值投资的概念底座。点任意术语即查；用自己的话讲对了才算「掌握」。全站按 <kbd>⌘K</kbd> 也能速查。
        </p>
      </div>
      <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap", marginBottom: 8 }}>
        <input className="vi-in" value={q} onChange={(e) => setQ(e.target.value)} placeholder="搜术语 (中文 / English)…" style={{ flex: 1, minWidth: 200 }} />
        <span className="status">{all.length} 个术语 · 已掌握 {masteredN}</span>
      </div>
      {Object.entries(byCat).map(([cat, items]) => (
        <div key={cat}>
          <h2 style={{ fontSize: 16, margin: "28px 0 10px", color: "var(--accent)", borderBottom: "1px solid var(--border)", paddingBottom: 6 }}>{cat}</h2>
          <div className="vi-grid">
            {items.map((t, i) => (
              <motion.div
                key={t.slug}
                className="vi-card hoverable"
                style={{ cursor: "pointer" }}
                onClick={() => openTerm(t.slug)}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.4, delay: Math.min(i, 8) * 0.03, ease: [0.16, 1, 0.3, 1] }}
              >
                <h3>
                  {t.term} {t.mastery === "mastered" && <span className="read-dot" title="已掌握">✓</span>}
                  {t.learned && (
                    <span className="vi-ex-draft" title="划词草稿，核对后再标掌握">划词·草稿</span>
                  )}
                  {t.term_en && <span style={{ color: "var(--muted)", fontSize: 13, fontWeight: 400 }}> {t.term_en}</span>}
                </h3>
                <p>{(t.definition || "").slice(0, 80)}</p>
              </motion.div>
            ))}
          </div>
        </div>
      ))}
    </>
  );
}
