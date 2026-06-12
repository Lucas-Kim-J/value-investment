import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { animate, motion } from "framer-motion";
import { apiGet } from "../lib/api";
import { useMe } from "../lib/hooks";
import type { AchievementsResp, CanonItem, LearningSummary } from "../lib/types";

const STAGE_CN: Record<string, string> = { novice: "学徒", building: "践行者", practitioner: "审视者" };

const MODULES: ReadonlyArray<{ href: string; title: string; sub: string }> = [
  { href: "/", title: "📖 方法论 v1.1", sub: "21 章核心方法论" },
  { href: "/canon", title: "📚 一手内容库", sub: "25 篇认知底座" },
  { href: "/doc/learning/valuation-cheatsheet", title: "📐 估值 4 工具", sub: "前 180 天禁 DCF" },
  { href: "/doc/learning/failure-cases", title: "⚠️ 失败案例", sub: "尸检 6 个崩盘" },
  { href: "/wiki", title: "🔍 术语 Wiki", sub: "即点即查" },
  { href: "/achievements", title: "🏅 成就与进度", sub: "证据驱动" },
];

interface NextStep { kicker: string; title: string; body: string; cta: string; href: string }

function computeNext(s: LearningSummary | null, pick: CanonItem | null): NextStep {
  const canon = s?.canon_read ?? 0;
  const terms = s?.term_mastered ?? 0;
  const holds = s?.stats.holdings ?? 0;
  const comp = s?.stats.company_analyzed ?? 0;
  let key = "canon";
  if (canon === 0) key = "canon";
  else if (terms < 3) key = "terms";
  else if (holds === 0) key = "hold";
  else if (comp === 0) key = "analyze";
  else key = "canon";
  if (key === "terms")
    return { kicker: "打术语底座", title: "把不懂的词查清楚——讲得出才算掌握", body: "读一手内容时遇到生词，全站 ⌘K 即查 / 划词→解释→收入术语库。", cta: "去术语 Wiki →", href: "/wiki" };
  if (key === "hold")
    return { kicker: "把学到的用起来", title: "把你的实仓录进来", body: "记录你买了什么 + thesis，让 hermes 按方法论审视你的纪律。", cta: "录入持仓 →", href: "/portfolio" };
  if (key === "analyze")
    return { kicker: "产出", title: "分析你的第一家公司", body: "hermes 按你现在的水平指出「该看什么、缺什么验证」，自动归档可回看。", cta: "去公司分析 →", href: "/analyze" };
  return {
    kicker: canon === 0 ? "从这里开始 · 打地基" : "继续打地基",
    title: canon === 0 ? "读一篇大师原始思维，写一句你自己的话" : "再读一篇起点必读，写一句你的话",
    body: "这是整套系统的地基——之后分析持仓和公司都靠它。",
    cta: pick ? `打开《${pick.title}》约 ${Math.round((pick.est_minutes || 0) / 60)}h →` : "打开一手内容库 →",
    href: "/canon",
  };
}

function CountStat({ n, label }: { n: number; label: string }) {
  const [v, setV] = useState(0);
  useEffect(() => {
    const controls = animate(0, n, { duration: 0.9, ease: "easeOut", onUpdate: (x) => setV(Math.round(x)) });
    return () => controls.stop();
  }, [n]);
  return (
    <div className="stat">
      <div className="n">{v.toLocaleString()}</div>
      <div className="l">{label}</div>
    </div>
  );
}

export default function Dashboard() {
  const user = useMe();
  const [summary, setSummary] = useState<LearningSummary | null>(null);
  const [ach, setAch] = useState<AchievementsResp | null>(null);
  const [pick, setPick] = useState<CanonItem | null>(null);

  useEffect(() => {
    if (!user) return;
    apiGet<LearningSummary>("/api/learning/summary").then((r) => setSummary(r.data));
    apiGet<AchievementsResp>("/api/achievements").then((r) => setAch(r.data));
    apiGet<{ items: CanonItem[] }>("/api/canon").then((r) => {
      const items = r.data?.items ?? [];
      const p =
        items.filter((i) => i.tier === "tier0" && !i.read).sort((a, b) => (a.est_minutes || 0) - (b.est_minutes || 0))[0] ||
        items.find((i) => i.tier === "tier0") ||
        null;
      setPick(p);
    });
  }, [user]);

  const next = computeNext(summary, pick);
  const rise = (i = 0) => ({
    initial: { opacity: 0, y: 14 },
    animate: { opacity: 1, y: 0 },
    transition: { duration: 0.5, delay: i * 0.05, ease: [0.16, 1, 0.3, 1] as const },
  });

  return (
    <>
      <motion.div className="app-head" {...rise(0)}>
        <div className="eyebrow">Value Investing Learning OS</div>
        <h1 className="shiny">{user ? `欢迎回来，${user}` : "价值投资学习 OS"}</h1>
        <p>学一手内容 → 留痕 + 验证 → 这些成为你分析持仓与公司的认知底座 → hermes 随你成长给个性化审视。</p>
      </motion.div>

      {user && summary ? (
        <motion.div className="stat-row" {...rise(1)}>
          <div className="stat">
            <div className="n"><span className="stage-chip">{STAGE_CN[summary.stage] || summary.stage}</span></div>
            <div className="l">段位</div>
          </div>
          <CountStat n={summary.canon_read} label="读过一手内容" />
          <CountStat n={summary.term_mastered} label="掌握术语" />
          <CountStat n={ach?.unlocked_count ?? 0} label="解锁成就" />
        </motion.div>
      ) : !user ? (
        <motion.div className="login-prompt" {...rise(1)}>
          🔒 <Link to="/login">登录</Link> 后开启学习留痕、成就与个性化分析。只读学习内容无需登录。
        </motion.div>
      ) : null}

      <motion.div className="next-card" {...rise(2)}>
        <div className="next-kicker">👉 {next.kicker}</div>
        <h2 className="next-title">{next.title}</h2>
        <p className="next-body">{next.body}</p>
        <div className="next-cta">
          <Link className="btn btn-primary" to={next.href}>{next.cta}</Link>
          <Link className="next-alt" to="/learn">看完整学习路线 →</Link>
        </div>
      </motion.div>

      <div className="section-t">全部模块</div>
      <div className="vi-grid" style={{ gridTemplateColumns: "repeat(auto-fill,minmax(200px,1fr))" }}>
        {MODULES.map((m, i) => (
          <motion.div key={m.href + m.title} {...rise(3 + i)}>
            <Link className="vi-card" to={m.href} style={{ display: "block" }}>
              <h3>{m.title}</h3>
              <p style={{ fontSize: 12.5 }}>{m.sub}</p>
            </Link>
          </motion.div>
        ))}
      </div>
    </>
  );
}
