import { useEffect, useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { apiGet } from "../lib/api";
import { useMe } from "../lib/hooks";
import { useShell, usePageContext } from "../shell/ShellContext";
import type { CanonItem, Holding } from "../lib/types";
import { CanonModal } from "./CanonModal";

const KINDS: Record<string, string> = { letter: "Letter 信", agm: "AGM 股东会", "13f": "13F 持仓", quarterly: "季报/10-K", talk: "演讲/访谈", book: "书", memo: "备忘录", tool: "工具源" };
const TIERS: Record<string, string> = { tier0: "起点必读", tier1: "核心", tier2: "拓展" };

export default function Canon() {
  const user = useMe();
  const { openTerm, celebrate } = useShell();
  const [items, setItems] = useState<CanonItem[]>([]);
  const [holdings, setHoldings] = useState<Holding[]>([]);
  const [kind, setKind] = useState("all");
  const [tier, setTier] = useState("all");
  const [open, setOpen] = useState<string | null>(null);

  useEffect(() => {
    apiGet<{ items: CanonItem[] }>("/api/canon").then((r) => setItems(r.data?.items ?? []));
  }, []);
  useEffect(() => {
    if (user) apiGet<{ holdings: Holding[] }>("/api/holdings").then((r) => setHoldings(r.data?.holdings ?? []));
  }, [user]);

  usePageContext(() => {
    const lines = items.map((i) =>
      `- [${TIERS[i.tier] || i.tier}] ${i.title}（${KINDS[i.kind] || i.kind}，约${Math.round((i.est_minutes || 0) / 60)}h）${i.read ? "[已开始]" : ""}：${(i.why || "").replace(/\s+/g, " ").slice(0, 55)}`);
    return `页面：一手内容库（大师一手内容清单，按层级，越前越基础）。用户已开始 ${items.filter((x) => x.read).length}/${items.length} 篇。\n清单：\n${lines.join("\n")}`;
  });

  const kinds = useMemo(() => ["all", ...Array.from(new Set(items.map((i) => i.kind)))], [items]);
  const filtered = items.filter((i) => (kind === "all" || i.kind === kind) && (tier === "all" || i.tier === tier));
  const readN = items.filter((i) => i.read).length;
  const firstPick = useMemo(
    () => items.filter((i) => i.tier === "tier0").sort((a, b) => (a.est_minutes || 0) - (b.est_minutes || 0))[0],
    [items],
  );

  function markRead(s: string) {
    setItems((xs) => xs.map((x) => (x.slug === s ? { ...x, read: true } : x)));
  }

  return (
    <>
      <div className="app-head">
        <div className="eyebrow">Primary Sources</div>
        <h1>一手内容库</h1>
        <p>letter / AGM / 13F / 季报 / 演讲 —— 大师们的原始思维，是你认知的底层框架，优先学它胜过二手解读。</p>
        <p style={{ fontSize: 13, color: "var(--muted)" }}>
          <span className="cov cov-guide">导读</span> 官方链接 + 我们的概念级读法（绝不含编造的数字/引文）。涉及具体数字，一律去官方原文核对。
        </p>
        <p className="status">共 {items.length} 篇 · 你已开始 {readN} 篇</p>
      </div>

      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 18 }}>
        {kinds.map((k) => (
          <button key={k} className="btn btn-ghost btn-sm" style={kind === k ? { borderColor: "var(--accent)", color: "var(--accent)" } : undefined} onClick={() => setKind(k)}>
            {k === "all" ? "全部" : KINDS[k] || k}
          </button>
        ))}
        <span style={{ width: 1, background: "var(--border)", margin: "0 4px" }} />
        {["all", "tier0", "tier1", "tier2"].map((t) => (
          <button key={t} className="btn btn-ghost btn-sm" style={tier === t ? { borderColor: "var(--accent)", color: "var(--accent)" } : undefined} onClick={() => setTier(t)}>
            {t === "all" ? "全部层级" : TIERS[t]}
          </button>
        ))}
      </div>

      {readN === 0 && firstPick && (
        <div className="start-hint">
          📍 不知道从哪开始？先挑一篇短的「起点必读」：
          <a href="#" onClick={(e) => { e.preventDefault(); setOpen(firstPick.slug); }}>{firstPick.title}（约 {Math.round((firstPick.est_minutes || 0) / 60)}h）</a>
          ，读完写一句你自己的话就能留痕。也可以点右下角 💬 让 hermes 按你的水平排个顺序。
        </div>
      )}

      <div className="vi-grid">
        {filtered.map((i, idx) => (
          <motion.div
            key={i.slug}
            className="vi-card hoverable"
            style={{ cursor: "pointer" }}
            onClick={() => setOpen(i.slug)}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: Math.min(idx, 8) * 0.03, ease: [0.16, 1, 0.3, 1] }}
          >
            <div style={{ marginBottom: 8 }}>
              <span className="kind-tag">{KINDS[i.kind] || i.kind}</span>
              <span className="cov cov-guide">导读</span> {i.read && <span className="read-dot" title="已开始">●</span>}
            </div>
            <h3>{i.title}</h3>
            <p>{i.why}</p>
            <div className="meta">{i.source} · {i.period} · {TIERS[i.tier] || i.tier} · 约 {Math.round((i.est_minutes || 0) / 60)}h</div>
          </motion.div>
        ))}
      </div>

      <AnimatePresence>
        {open && (
          <CanonModal
            key={open}
            slug={open}
            user={user ?? null}
            holdings={holdings}
            onClose={() => setOpen(null)}
            onPick={openTerm}
            onCelebrate={celebrate}
            onRead={markRead}
          />
        )}
      </AnimatePresence>
    </>
  );
}
