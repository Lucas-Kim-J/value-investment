import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { apiGet } from "../lib/api";
import { useMe } from "../lib/hooks";
import type { Achievement, AchievementsResp, LearningSummary } from "../lib/types";

const STAGE_CN: Record<string, string> = { novice: "学徒", building: "践行者", practitioner: "审视者" };

export default function Achievements() {
  const user = useMe();
  const [summary, setSummary] = useState<LearningSummary | null>(null);
  const [items, setItems] = useState<Achievement[]>([]);

  useEffect(() => {
    if (user) apiGet<LearningSummary>("/api/learning/summary").then((r) => setSummary(r.data));
    apiGet<AchievementsResp>("/api/achievements").then((r) => setItems(r.data?.items ?? []));
  }, [user]);

  return (
    <>
      <div className="app-head">
        <div className="eyebrow">Progress &amp; Achievements</div>
        <h1>成就与进度</h1>
        <p>
          成就只奖励<strong>可证伪的产出</strong>和<strong>事后被验证的判断</strong>——读完写下你的话、用费曼复述讲对术语、归档一份真实分析。<strong>刷不出来</strong>，也不奖励连续打卡或纯数量。
        </p>
      </div>
      {summary ? (
        <div className="stat-row">
          <div className="stat">
            <div className="n"><span className="stage-chip">{STAGE_CN[summary.stage] || summary.stage}</span></div>
            <div className="l">当前段位</div>
          </div>
          <div className="stat"><div className="n">{summary.canon_read}</div><div className="l">读过的一手内容</div></div>
          <div className="stat"><div className="n">{summary.term_mastered}</div><div className="l">掌握的术语</div></div>
          <div className="stat"><div className="n">{summary.total_hours}</div><div className="l">累计学时(h)</div></div>
        </div>
      ) : !user ? (
        <p className="status">登录后查看你的进度与成就。 <Link to="/login">去登录</Link></p>
      ) : null}
      <h2 style={{ fontSize: 17, margin: "30px 0 14px", borderBottom: "1px solid var(--border)", paddingBottom: 8 }}>成就</h2>
      <div className="vi-grid">
        {items.map((a, i) => (
          <motion.div
            key={a.key}
            className="vi-card"
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: a.unlocked ? 1 : 0.5, y: 0 }}
            transition={{ duration: 0.4, delay: Math.min(i, 8) * 0.03, ease: [0.16, 1, 0.3, 1] }}
          >
            <div style={{ fontSize: 26, marginBottom: 6 }}>{a.icon || "🏅"}</div>
            <h3>{a.title} {a.unlocked && <span className="read-dot">✓</span>}</h3>
            <p>{a.description}</p>
            <div className="meta">
              {a.unlocked ? "解锁于 " + (a.unlocked_at ? new Date(a.unlocked_at).toLocaleDateString("zh-CN") : "") : "未解锁"}
            </div>
          </motion.div>
        ))}
      </div>
      <div style={{ marginTop: 34, padding: "16px 18px", background: "var(--bg-soft)", border: "1px dashed var(--border)", borderRadius: 10, color: "var(--fg-soft)", fontSize: 13.5, lineHeight: 1.6 }}>
        <strong>进阶成就（设计中）</strong>：thesis 兑现率（你写下「X 事件发生则证明我错」，到期回看是否应验）、「我改变了主意」（记录证据驱动的观点转向）、错误归档（把自己的判断错误写进个人失败案例）。这些需要「时间检验」，无法当下刷出，是真正衡量学习的硬指标。
      </div>
    </>
  );
}
