import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiGet, apiPost } from "../lib/api";
import { useMe } from "../lib/hooks";
import { Markdown } from "../shell/Markdown";
import type { MarketBoard, MarketCycle, MarketRates, MarketSentiment, MarketReview } from "../lib/types";
import { CycleCompass } from "./market/CycleCompass";
import "./analyze/dashboard.css";
import "./market/market.css";

const heatCls = (q: string) => (q === "领先" ? "cheap" : q === "落后" ? "rich" : "fair");
// valuation: 极贵(level4)=red caution, 便宜(level1)=green, else amber
const valCls = (lvl?: number | null) => (lvl == null ? "na" : lvl >= 4 ? "rich" : lvl <= 1 ? "cheap" : "fair");
// rate path: 降息(easing)=green, 加息/偏紧=red, 持平=amber
const pathCls = (d?: string) => (!d ? "na" : d.includes("降息") ? "cheap" : d.includes("加息") || d.includes("偏紧") ? "rich" : "fair");
// sentiment contrarian: extreme fear(≤2)=green opportunity, greed(≥4)=red caution
const fgCls = (lvl?: number | null) => (lvl == null ? "na" : lvl <= 2 ? "cheap" : lvl >= 4 ? "rich" : "fair");
const ratingCls = (r: string) => (r.includes("恐惧") ? "cheap" : r.includes("贪婪") ? "rich" : "fair");
const pct = (x?: number | null) => (x == null ? "—" : x + "%");
const signed = (x?: number | null) => (x == null ? "—" : (x > 0 ? "+" : "") + x + "%");

export default function Market() {
  const user = useMe();
  const nav = useNavigate();
  const [board, setBoard] = useState<MarketBoard | null>(null);
  const [cycle, setCycle] = useState<MarketCycle | null>(null);
  const [rates, setRates] = useState<MarketRates | null>(null);
  const [sentiment, setSentiment] = useState<MarketSentiment | null>(null);
  const [review, setReview] = useState<MarketReview | null>(null);
  const [genBusy, setGenBusy] = useState(false);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    let on = true;
    apiGet<MarketCycle>("/api/market/cycle?market=美股").then((r) => { if (on) setCycle(r.data); });
    apiGet<MarketRates>("/api/market/rates?market=美股").then((r) => { if (on) setRates(r.data); });
    apiGet<MarketSentiment>("/api/market/sentiment?market=美股").then((r) => { if (on) setSentiment(r.data); });
    apiGet<MarketReview>("/api/market/review").then((r) => { if (on) setReview(r.data); });
    apiGet<MarketBoard>("/api/market/board?market=美股").then((r) => {
      if (r.status === 401) { nav("/login", { replace: true }); return; }
      if (on) { setBoard(r.data); setLoaded(true); }
    });
    return () => { on = false; };
  }, [nav]);

  async function genReview() {
    if (genBusy) return;
    setGenBusy(true);
    setReview({ status: "running" });
    await apiPost("/api/market/review", {});
    for (let i = 0; i < 80; i++) {                       // poll up to ~6.5 min
      await new Promise((r) => setTimeout(r, 5000));
      const r = await apiGet<MarketReview>("/api/market/review");
      if (r.data && r.data.status !== "running") { setReview(r.data); break; }
      setReview(r.data);
    }
    setGenBusy(false);
  }

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

      {rates && (rates.policy_rates?.length > 0 || rates.future_path?.market_implied) && (
        <div className="ca-panel ca-consensus">
          <h3 style={{ margin: 0 }}>🏛️ 利率与央行（美股）</h3>
          <p className="hint">当前政策利率 + 未来路径双腿（市场隐含 vs Fed 点阵图，两者都是真实数据、非预测）+ 关键宏观。</p>
          <div className="mk-rates">
            {rates.policy_rates.map((r, i) => (
              <div className="mk-rate" key={i}>
                <div className="rn">{r.name}</div>
                <div className="rv">{r.value}</div>
                {r.detail && <div className="rd">{r.detail}</div>}
              </div>
            ))}
          </div>
          <div className="ca-tools" style={{ marginTop: 12 }}>
            {rates.future_path?.market_implied && (
              <div className="ca-tool">
                <div className="tn">未来 · 腿A 市场隐含 <span className={"ca-verdict " + pathCls(rates.future_path.market_implied.direction)}>{rates.future_path.market_implied.direction}</span></div>
                <div className="td">{rates.future_path.market_implied.note}</div>
              </div>
            )}
            {rates.future_path?.dot_plot && (
              <div className="ca-tool">
                <div className="tn">未来 · 腿B Fed点阵图 <span className={"ca-verdict " + pathCls(rates.future_path.dot_plot.direction)}>{rates.future_path.dot_plot.direction}</span></div>
                <div className="td">{rates.future_path.dot_plot.note}</div>
              </div>
            )}
          </div>
          {rates.future_path?.comparison && <div className="ca-bet">{rates.future_path.comparison}</div>}
          {rates.macro?.length > 0 && (
            <div className="mk-rates" style={{ marginTop: 4 }}>
              {rates.macro.map((m, i) => (
                <div className="mk-rate" key={i}>
                  <div className="rn">{m.name}</div>
                  <div className="rv">{m.value}</div>
                  {m.trend && <div className="rd">{m.trend}</div>}
                </div>
              ))}
            </div>
          )}
          {(rates.warnings?.length ?? 0) > 0 && <p className="hint" style={{ marginTop: 8 }}>{rates.warnings.join("；")}</p>}
        </div>
      )}

      {sentiment && (sentiment.fear_greed?.score != null || sentiment.vix_term?.label !== "数据缺失") && (
        <div className="ca-panel ca-consensus">
          <h3 style={{ margin: 0 }}>😱 情绪体温计（美股）</h3>
          <p className="hint">逆向读：极度恐惧常在底部、极度贪婪常在过热。{sentiment.composite?.note}</p>
          <div className="mk-gauges">
            <div className="mk-gauge">
              <div className="g-h">CNN 恐惧贪婪 <span className={"ca-verdict " + fgCls(sentiment.fear_greed?.level)}>{sentiment.fear_greed?.label}</span></div>
              <div className="g-big">{sentiment.fear_greed?.score ?? "—"}<span className="g-u"> / 100</span></div>
              {sentiment.fear_greed?.contrarian && <div className="g-note" style={{ color: "var(--fg-soft)" }}>{sentiment.fear_greed.contrarian}</div>}
            </div>
            <div className="mk-gauge">
              <div className="g-h">VIX 期限结构</div>
              <div className="g-big" style={{ fontSize: 18 }}>{sentiment.vix_term?.label}</div>
              {sentiment.vix_term?.detail && <div className="g-sub">{sentiment.vix_term.detail}</div>}
            </div>
          </div>
          {(sentiment.fear_greed?.subs?.length ?? 0) > 0 && (
            <div className="ca-tilt">
              <span className="hint" style={{ margin: 0 }}>恐惧贪婪分项：</span>
              {sentiment.fear_greed!.subs!.map((s, i) => (
                <span key={i} className={"ca-verdict " + ratingCls(s.rating)}>{s.name}·{s.rating}</span>
              ))}
            </div>
          )}
        </div>
      )}

      <div className="ca-panel ca-consensus">
        <div style={{ display: "flex", alignItems: "baseline", gap: 10, flexWrap: "wrap" }}>
          <h3 style={{ margin: 0 }}>🧠 市场审视（AI · 共识 / 历史镜像 / 非共识）</h3>
          <button className="ca-refresh" disabled={genBusy || review?.status === "running"} onClick={genReview}>
            {genBusy || review?.status === "running" ? "生成中…（约 1 分钟）" : review?.report ? "🔄 重新生成" : "🧠 生成市场审视"}
          </button>
        </div>
        <p className="hint">把上面全部真实市场数据 + 一手观点（播客信号卡）综合成：当前共识&为什么 / 历史镜像 / 市场级非共识 + 反证。不预测点位、不荐股。</p>
        {review?.status === "error" && <p className="status err">生成失败：{review.error}</p>}
        {review?.report
          ? <div style={{ marginTop: 6 }}><Markdown>{review.report}</Markdown></div>
          : (genBusy || review?.status === "running")
            ? <div className="ca-skel" style={{ textAlign: "left", padding: "10px 0" }}>AI 正在综合市场数据…（约 1 分钟）</div>
            : <p className="hint">点上方按钮，基于当前市场数据生成一次审视。</p>}
      </div>

      <CycleCompass cycle={cycle} />
    </>
  );
}
