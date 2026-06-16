import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiGet } from "../lib/api";
import { useMe } from "../lib/hooks";
import type { MarketBoard, MarketCycle } from "../lib/types";
import { CycleCompass } from "./market/CycleCompass";
import "./analyze/dashboard.css";
import "./market/market.css";

const heatCls = (q: string) => (q === "领先" ? "cheap" : q === "落后" ? "rich" : "fair");
// valuation: 极贵(level4)=red caution, 便宜(level1)=green, else amber
const valCls = (lvl?: number | null) => (lvl == null ? "na" : lvl >= 4 ? "rich" : lvl <= 1 ? "cheap" : "fair");
const pct = (x?: number | null) => (x == null ? "—" : x + "%");
const signed = (x?: number | null) => (x == null ? "—" : (x > 0 ? "+" : "") + x + "%");

export default function Market() {
  const user = useMe();
  const nav = useNavigate();
  const [board, setBoard] = useState<MarketBoard | null>(null);
  const [cycle, setCycle] = useState<MarketCycle | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    let on = true;
    apiGet<MarketCycle>("/api/market/cycle?market=美股").then((r) => { if (on) setCycle(r.data); });
    apiGet<MarketBoard>("/api/market/board?market=美股").then((r) => {
      if (r.status === 401) { nav("/login", { replace: true }); return; }
      if (on) { setBoard(r.data); setLoaded(true); }
    });
    return () => { on = false; };
  }, [nav]);

  const v = board?.valuation, c = board?.concentration, b = board?.breadth, t = board?.temperature;

  return (
    <>
      <div className="app-head">
        <div className="eyebrow">VALUE INVESTING · 自上而下</div>
        <h1>🌐 市场</h1>
        <p>先看天气再选种子：市场贵不贵、钱多不多、广度好不好、哪个板块在领跑/拥挤、周期顺不顺风——单股价值判断要叠在这张图上看。</p>
      </div>

      {user === null && <p className="status">登录后查看市场看板。</p>}
      {user && !loaded && <p className="status">加载中…（首次计算广度需扫描标普成分，约 1 分钟）</p>}

      {board && (
        <>
          <div className="ca-panel ca-consensus">
            <h3 style={{ margin: 0 }}>🌡️ 市场体温计（美股）</h3>
            {t?.note && <p className="hint">{t.note}</p>}
            <div className="mk-gauges">
              <div className="mk-gauge">
                <div className="g-h">市场估值 <span className={"ca-verdict " + valCls(v?.level)}>{v?.label}</span></div>
                <div className="g-big">{pct(v?.percentile)}<span className="g-u"> 历史分位</span></div>
                <div className="g-sub">{[v?.pe ? `S&P P/E ${v.pe.value}` : "", v?.cape ? `CAPE ${v.cape.value}` : ""].filter(Boolean).join(" · ") || "—"}</div>
                {v?.note && <div className="g-note">{v.note}</div>}
              </div>
              <div className="mk-gauge">
                <div className="g-h">集中度 <span className={"ca-verdict " + (c?.concentrated ? "rich" : "fair")}>{c?.label}</span></div>
                <div className="g-big">{pct(c?.top_n_weight)}<span className="g-u"> 前{c?.top_n}大权重</span></div>
                <div className="g-sub">{c?.detail || "—"}</div>
              </div>
              <div className="mk-gauge">
                <div className="g-h">市场广度 <span className={"ca-verdict " + (b?.healthy ? "cheap" : b?.healthy === false ? "rich" : "na")}>{b?.label}</span></div>
                <div className="g-big">{pct(b?.pct_above_200)}<span className="g-u"> 个股&gt;200日线</span></div>
                <div className="g-sub">{b?.pct_above_50 != null ? `${b.pct_above_50}% >50日线` : ""}{b?.n ? ` · ${b.n} 只` : ""}</div>
              </div>
            </div>
          </div>

          {board.sectors?.length > 0 && (
            <div className="ca-panel ca-consensus">
              <h3 style={{ margin: 0 }}>🔥 板块热力图（相对强度 · 近6月/3月 vs 标普）</h3>
              <p className="hint">谁在领跑、谁在拥挤：按相对强度排序。领先=强且在加速，落后=弱。{board.crowding_note}</p>
              <div className="mk-heat">
                {board.sectors.map((s) => (
                  <div key={s.ticker} className={"mk-sector " + heatCls(s.quadrant)}>
                    <div className="s-n">{s.name}<span className="s-t">{s.ticker}</span></div>
                    <div className="s-heat">{signed(s.heat)}</div>
                    <div className="s-q">{s.quadrant}</div>
                    <div className="s-rs">6月 {signed(s.rs_6m)} · 3月 {signed(s.rs_3m)}</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {(board.warnings?.length ?? 0) > 0 && <p className="hint" style={{ padding: "0 4px" }}>{board.warnings.join("；")}</p>}
        </>
      )}

      <CycleCompass cycle={cycle} />
    </>
  );
}
