import { type KeyboardEvent, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { apiGet } from "../lib/api";
import type { GlossaryTerm } from "../lib/types";

export function Cmdk({ onClose, onPick }: { onClose: () => void; onPick: (s: string) => void }) {
  const [terms, setTerms] = useState<GlossaryTerm[]>([]);
  const [q, setQ] = useState("");
  const [sel, setSel] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    apiGet<{ items: GlossaryTerm[] }>("/api/terms").then((r) => setTerms(r.data?.items ?? []));
    setTimeout(() => inputRef.current?.focus(), 30);
  }, []);

  const filtered = useMemo(() => {
    const s = q.trim().toLowerCase();
    if (!s) return terms.slice(0, 8);
    return terms
      .filter((t) => (t.term || "").toLowerCase().includes(s) || (t.term_en || "").toLowerCase().includes(s) || (t.slug || "").includes(s))
      .slice(0, 20);
  }, [q, terms]);
  useEffect(() => setSel(0), [q]);

  function onKey(e: KeyboardEvent) {
    if (e.key === "ArrowDown") {
      setSel((s) => Math.min(s + 1, filtered.length - 1));
      e.preventDefault();
    } else if (e.key === "ArrowUp") {
      setSel((s) => Math.max(s - 1, 0));
      e.preventDefault();
    } else if (e.key === "Enter" && filtered[sel]) {
      onPick(filtered[sel].slug);
    } else if (e.key === "Escape") {
      onClose();
    }
  }

  return (
    <motion.div
      className="vi-modal-bg vi-cmdk"
      style={{ alignItems: "flex-start", paddingTop: 80 }}
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <motion.div className="vi-modal" style={{ maxWidth: 560 }} initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }}>
        <input ref={inputRef} className="cmdk-input" value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={onKey} placeholder="搜术语… (中文 / English)" autoComplete="off" />
        <div className="cmdk-results">
          {filtered.length === 0 ? (
            <div className="cmdk-empty">
              没有匹配的术语。试试英文，或去 <Link to="/wiki" onClick={onClose}>术语 Wiki</Link> 浏览。
            </div>
          ) : (
            filtered.map((t, i) => (
              <div key={t.slug} className={"cmdk-item" + (i === sel ? " sel" : "")} onClick={() => onPick(t.slug)} onMouseEnter={() => setSel(i)}>
                <div className="t">
                  {t.term}
                  {t.term_en && <span className="en">{t.term_en}</span>}
                </div>
                <div className="d">{(t.definition || "").slice(0, 90)}</div>
                {t.category && <div className="cat">{t.category}</div>}
              </div>
            ))
          )}
        </div>
      </motion.div>
    </motion.div>
  );
}
