import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { apiGet } from "../lib/api";
import { useMe } from "../lib/hooks";
import type { LearningSummary } from "../lib/types";

interface Stage { n: string; key: string; name: string; prog: string; why: string; links: [string, string][] }

export default function Learn() {
  const user = useMe();
  const [s, setS] = useState<LearningSummary | null>(null);
  useEffect(() => {
    if (user) apiGet<LearningSummary>("/api/learning/summary").then((r) => setS(r.data));
  }, [user]);

  const canon = s?.canon_read ?? 0;
  const terms = s?.term_mastered ?? 0;
  const holds = s?.stats.holdings ?? 0;
  const comp = s?.stats.company_analyzed ?? 0;
  let here = "canon";
  if (canon === 0) here = "canon";
  else if (terms < 3) here = "terms";
  else if (holds === 0) here = "hold";
  else if (comp === 0) here = "analyze";
  else here = "canon";

  const stages: Stage[] = [
    { n: "①", key: "frame", name: "🧭 建立框架", prog: "基本盘 · 随时可读", why: "先有地图再上路：方法论 + 估值工具 + 失败案例，建立判断的底层框架。",
      links: [["/", "方法论 v1.1"], ["/doc/learning/valuation-cheatsheet", "估值 4 工具（前 180 天禁 DCF）"], ["/doc/learning/failure-cases", "失败案例研究"]] },
    { n: "②", key: "canon", name: "📚 学一手内容", prog: canon ? `已开始 ${canon} 篇` : "0 篇", why: "大师原始思维 = 认知底座。从 Tier0 起点必读挑短的开始，读完写一句你自己的话。",
      links: [["/canon", "一手内容库"], ["/doc/learning/canon-reading", "经典文本清单（13 本/套）"]] },
    { n: "③", key: "terms", name: "🔍 打术语底座", prog: `已掌握 ${terms} 个`, why: "读到不懂的词 ⌘K 即查 / 划词→解释→收入术语库。用自己的话讲对了才算掌握。",
      links: [["/wiki", "术语 Wiki"]] },
    { n: "④", key: "hold", name: "💼 管你的仓", prog: holds ? `${holds} 个持仓` : "输入端口", why: "把 ①②③ 学到的用在真仓位上。录入 → hermes 按方法论审视你的纪律。",
      links: [["/portfolio", "录入持仓 / 生成规范报告"]] },
    { n: "⑤", key: "analyze", name: "🏢 做公司分析", prog: comp ? `${comp} 次分析` : "产出", why: "按你当前阶段分析一家公司，自动归档可回看演进（可从持仓一键带入）。",
      links: [["/analyze", "公司分析"]] },
  ];

  return (
    <>
      <div className="app-head">
        <div className="eyebrow">Learning Map</div>
        <h1>学习路线</h1>
        <p>
          想从哪开始都行，但这是建立框架最稳的顺序。①②③ 是认知底座，喂给 ④ 持仓审视和 ⑤ 公司分析。
          {!user && (<> <Link to="/login">登录</Link> 后会按你的进度高亮「你在这里」。</>)}
        </p>
      </div>
      {stages.map((z, i) => (
        <motion.div
          key={z.key}
          className={"route-stage" + (z.key === here && user ? " here" : "")}
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.45, delay: i * 0.05, ease: [0.16, 1, 0.3, 1] }}
        >
          <h3>
            <span className="rs-num">{z.n}</span> {z.name} <span className="rs-prog">{z.prog}</span>
            {z.key === here && user && <span className="rs-here">● 你在这里</span>}
          </h3>
          <p>{z.why}</p>
          <div className="rs-links">
            {z.links.map(([to, label]) => (
              <Link key={to + label} to={to}>{label} →</Link>
            ))}
          </div>
        </motion.div>
      ))}
      <div className="route-tie">
        🔗 <strong>怎么串起来：</strong>读一手内容（②）时遇到生词就去打底（③）；学到的框架用在你的真仓位上（④）；再按你的水平做公司分析（⑤）。不确定先看哪站？右下角问 hermes 让它按你的进度排序。
      </div>

      <div className="section-t">执行节奏</div>
      <div className="vi-grid" style={{ gridTemplateColumns: "repeat(auto-fill,minmax(220px,1fr))" }}>
        {([
          ["/doc/routine/glossary", "📑 Routine 模板", "每日 / 每周 / 每月 / 每季 + 熔断机制。"],
          ["/doc/learning/progress-tracker", "📊 学习路径追踪", "90 / 270 / 720 天进度。"],
          ["/doc/product-vision", "🧭 产品理念", "这套「学习驱动」产品的设计逻辑与不可动摇的原则。"],
        ] as const).map(([to, title, sub]) => (
          <Link key={to} className="vi-card hoverable" to={to} style={{ display: "block" }}>
            <h3>{title}</h3>
            <p>{sub}</p>
          </Link>
        ))}
      </div>
    </>
  );
}
