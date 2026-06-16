import type { MarketCycle } from "../../lib/types";

// cycle: risk-on (level≥4) = green, late/neutral = amber, risk-off (≤2) = red
const cyclePosCls = (lvl?: number | null) => (lvl == null ? "na" : lvl >= 4 ? "cheap" : lvl <= 2 ? "rich" : "fair");
const lensCls = (s?: number | null) => (s == null ? "na" : s > 0 ? "cheap" : s < 0 ? "rich" : "fair");
const tiltCls = (v: string) => (v === "✓" ? "cheap" : v === "✕" ? "rich" : "fair");

/** Full top-down cycle compass panel (5 lenses + CAPE cap flag + regime asset tilt). */
export function CycleCompass({ cycle }: { cycle: MarketCycle | null }) {
  const comp = cycle?.composite;
  if (cycle && !comp?.position && (cycle.warnings?.length ?? 0) > 0) {
    return (
      <div className="ca-panel ca-consensus">
        <h3 style={{ margin: 0 }}>🧭 市场周期罗盘</h3>
        <div className="ca-skel" style={{ textAlign: "left", padding: "10px 0" }}>{cycle.warnings[0]}</div>
      </div>
    );
  }
  if (!cycle || !comp?.position) return null;
  return (
    <div className="ca-panel ca-consensus">
      <div style={{ display: "flex", alignItems: "baseline", gap: 10, flexWrap: "wrap" }}>
        <h3 style={{ margin: 0 }}>🧭 市场周期罗盘（{cycle.market}）</h3>
        <span className={"ca-verdict " + cyclePosCls(comp.level)}>{comp.position}</span>
        <span className={"ca-deep " + (comp.tailwind === "顺风" ? "yes" : "no")}>周期对风险资产：{comp.tailwind}</span>
        {cycle.recession_prob != null && (
          <span className="hint" style={{ margin: 0 }}>· 衰退概率(曲线估) {cycle.recession_prob}%</span>
        )}
      </div>
      <p className="hint">自上而下看周期：现在在周期哪一段、对风险资产顺风还是逆风。判断对、若处在差周期回报也有限——叠加周期看仓位/风格。</p>
      {cycle.cape_flag?.on && <div className="ca-bet">★ {cycle.cape_flag.note}</div>}
      <div className="ca-tools">
        {cycle.lenses.map((l, i) => (
          <div className="ca-tool" key={i}>
            <div className="tn">{l.title} <span className={"ca-verdict " + lensCls(l.score)}>{l.label}</span></div>
            <div className="td">{l.detail || (l.score == null ? "数据缺失" : "")}</div>
          </div>
        ))}
      </div>
      <div className="ca-tilt">
        <span className="hint" style={{ margin: 0 }}>当前 regime 资产倾向：</span>
        {Object.entries(cycle.asset_tilt).map(([k, v]) => (
          <span key={k} className={"ca-verdict " + tiltCls(v)}>{v} {k}</span>
        ))}
      </div>
      {(cycle.warnings?.length ?? 0) > 0 && <p className="hint" style={{ marginTop: 8 }}>{cycle.warnings.join("；")}</p>}
    </div>
  );
}
