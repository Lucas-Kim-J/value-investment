import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { motion } from "framer-motion";
import { apiGet, apiPost } from "../lib/api";
import { useMe } from "../lib/hooks";
import type { AnalysisDetail, AnalysisItem, CompanyNews, CompanyNewsItem, CompanyPeers, CompanySnapshot, Holding } from "../lib/types";
import { Markdown } from "../shell/Markdown";
import { EChart } from "./analyze/EChart";
import { fmtMoney, fmtPct, fmtPx, fmtX, priceOption, radarOption, relTime, trendOption } from "./analyze/charts";
import "./analyze/dashboard.css";

const MARKETS = ["美股", "A股", "港股", "加密"];

const verdictCls = (v: string) =>
  v === "便宜" ? "cheap" : v === "偏贵" ? "rich" : v === "合理" ? "fair" : "na";
const pcStr = (x?: number | null) => (x == null ? "数据缺失" : (x * 100).toFixed(1) + "%");
const mispCls = (f?: string | null) => (!f ? "na" : f.includes("错杀") ? "cheap" : f.includes("高估") ? "rich" : "fair");
// percentile cell color: for valuation lower=cheaper(good-ish), for quality higher=better. neutral chip.
const pctChip = (v?: number | null) => (v == null ? "—" : v + "%");

function Tile({ k, v, sub }: { k: string; v: string | null; sub?: string }) {
  const na = v == null || v === "";
  return (
    <div className="ca-tile">
      <div className="k">{k}</div>
      <div className={"v" + (na ? " na" : "")}>{na ? "—" : v}</div>
      {sub && !na && <div className="vsub">{sub}</div>}
    </div>
  );
}

function FeedItem({ it }: { it: CompanyNewsItem }) {
  const t = it.time ? new Date(it.time) : null;
  const when = t && !isNaN(t.getTime()) ? t.toLocaleDateString("zh-CN") : it.time || "";
  const meta = [it.publisher, when].filter(Boolean).join(" · ");
  return (
    <a className="ca-item" href={it.link || "#"} target="_blank" rel="noopener noreferrer">
      <div className="t">
        {it.type === "filing" && <span className="ca-badge">{it.form || "文件"}</span>}
        {it.title}
      </div>
      {meta && <div className="m">{meta}</div>}
    </a>
  );
}

export default function Analyze() {
  const user = useMe();
  const nav = useNavigate();
  const [params] = useSearchParams();

  const [ticker, setTicker] = useState("");
  const [name, setName] = useState("");
  const [market, setMarket] = useState("美股");

  const [snap, setSnap] = useState<CompanySnapshot | null>(null);
  const [news, setNews] = useState<CompanyNews | null>(null);
  const [peers, setPeers] = useState<CompanyPeers | null>(null);
  const [peersLoading, setPeersLoading] = useState(false);
  const [dashLoading, setDashLoading] = useState(false);
  const cur = useRef<{ ticker: string; name: string; market: string } | null>(null);

  // AI review (3-pillar hermes report, grounded on the data above)
  const [report, setReport] = useState<AnalysisDetail | null>(null);
  const [aiSt, setAiSt] = useState<{ msg: string; cls: string }>({ msg: "", cls: "" });
  const [aiBusy, setAiBusy] = useState(false);

  const [archive, setArchive] = useState<AnalysisItem[]>([]);
  const [holdings, setHoldings] = useState<Holding[]>([]);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; };
  }, []);
  useEffect(() => {
    if (user === null) nav("/login", { replace: true });
  }, [user, nav]);

  const radar = useMemo(() => (snap ? radarOption(snap.radar) : null), [snap]);
  const trend = useMemo(() => (snap ? trendOption(snap.financials) : null), [snap]);
  const price = useMemo(() => (snap ? priceOption(snap.price_history, snap.quote.currency) : null), [snap]);

  async function loadDashboard(t: string, n: string, mk: string, fresh = false) {
    cur.current = { ticker: t, name: n, market: mk };
    setDashLoading(true);
    setSnap(null);
    setNews(null);
    setPeers(null);
    setReport(null);
    setAiSt({ msg: "", cls: "" });
    const f = fresh ? "&fresh=1" : "";
    const qs = `ticker=${encodeURIComponent(t)}&market=${encodeURIComponent(mk)}&name=${encodeURIComponent(n || "")}`;
    // peers are slow (many .info calls) → fetch separately so the main dashboard isn't blocked
    setPeersLoading(true);
    apiGet<CompanyPeers>(`/api/companies/peers?${qs}${f}`).then((r) => {
      if (mounted.current) { setPeers(r.data); setPeersLoading(false); }
    });
    const [snapR, newsR] = await Promise.all([
      apiGet<CompanySnapshot>(`/api/companies/snapshot?${qs}${f}`),
      apiGet<CompanyNews>(`/api/companies/news?${qs}${f}`),
    ]);
    if (snapR.status === 401) { nav("/login", { replace: true }); return; }
    if (!mounted.current) return;
    setSnap(snapR.data);
    setNews(newsR.data);
    setDashLoading(false);
  }

  function go() {
    const t = ticker.trim();
    if (!t) return;
    loadDashboard(t, name.trim(), market);
  }
  function quick(h: Holding) {
    setTicker(h.ticker);
    setName(h.name || "");
    if (h.market) setMarket(h.market);
    loadDashboard(h.ticker, h.name || "", h.market || "美股");
  }

  // ---- AI review ----
  function showReport(d: AnalysisDetail) {
    if (!mounted.current) return;
    setReport(d);
    setAiSt({ msg: (d.ticker || "") + " · " + (d.generated_at ? new Date(d.generated_at).toLocaleString("zh-CN") : ""), cls: "ok" });
  }
  async function poll(id: number) {
    const t0 = Date.now();
    while (mounted.current && Date.now() - t0 < 200000) {
      await new Promise((r) => setTimeout(r, 3000));
      if (!mounted.current) return;
      let d: AnalysisDetail | null = null;
      try { d = (await apiGet<AnalysisDetail>("/api/analyses/" + id)).data; } catch { continue; }
      if (!d) continue;
      if (d.status === "done") { showReport(d); return; }
      if (d.status === "error") { setAiSt({ msg: "分析失败：" + (d.error || "未知"), cls: "err" }); return; }
      setAiSt({ msg: "分析中… " + Math.round((Date.now() - t0) / 1000) + "s", cls: "" });
    }
    if (mounted.current) setAiSt({ msg: "超时，请重试", cls: "err" });
  }
  async function startAI() {
    if (!cur.current) return;
    setAiBusy(true);
    setReport(null);
    setAiSt({ msg: "已提交，hermes 正按你的学习阶段审视…（约 30-90 秒）", cls: "" });
    try {
      const r = await apiPost<{ id: number; error?: string }>("/api/analyses", cur.current);
      if (r.status === 401) { nav("/login", { replace: true }); return; }
      if (!r.ok || !r.data?.id) { setAiSt({ msg: "启动失败：" + (r.data?.error || r.status), cls: "err" }); setAiBusy(false); return; }
      await poll(r.data.id);
    } catch (e) {
      setAiSt({ msg: "网络错误：" + (e as Error).message, cls: "err" });
    }
    if (mounted.current) setAiBusy(false);
    loadArchive();
  }

  // ---- archive ----
  async function loadArchive() {
    const r = await apiGet<{ items: AnalysisItem[] }>("/api/analyses");
    if (mounted.current) setArchive(r.data?.items ?? []);
  }
  async function openArchive(a: AnalysisItem) {
    await loadDashboard(a.ticker, a.company_name || "", a.market || "美股");
    window.scrollTo({ top: 0, behavior: "smooth" });
    const r = await apiGet<AnalysisDetail>("/api/analyses/" + a.id);
    if (r.data && r.data.status === "done") showReport(r.data);
  }

  // initial load
  useEffect(() => {
    if (!user) return;
    apiGet<{ holdings: Holding[] }>("/api/holdings").then((r) => { if (mounted.current) setHoldings(r.data?.holdings ?? []); });
    loadArchive();
    const t = params.get("ticker");
    if (t) {
      setTicker(t);
      const n = params.get("name") || "";
      const mk = params.get("market") || "美股";
      if (n) setName(n);
      if (params.get("market")) setMarket(mk);
      loadDashboard(t, n, mk);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user]);

  const p = snap?.profile, q = snap?.quote, m = snap?.metrics, vh = snap?.valuation_history;
  const ccy = q?.currency || p?.currency || "";
  const isCN = (snap?.market || "") === "A股";
  const range =
    q?.fifty_two_week_low != null && q?.fifty_two_week_high != null
      ? fmtPx(q.fifty_two_week_low, ccy) + " – " + fmtPx(q.fifty_two_week_high, ccy)
      : null;
  const valPctTile =
    vh?.pe_percentile != null ? `${vh.pe_percentile}%` : vh?.price_percentile != null ? `${vh.price_percentile}%` : null;
  const valPctSub = vh?.pe_percentile != null ? "P/E 历史分位" : vh?.price_percentile != null ? "价格历史分位" : "";

  return (
    <>
      <div className="app-head">
        <div className="eyebrow">Company Analysis</div>
        <h1>公司分析</h1>
        <p>
          先看<strong>真实数据</strong>——基本面、财务趋势、价格、一手消息流（美股 SEC / A股 巨潮公告优先）；再让 hermes 按
          <strong>你的学习阶段</strong>审视「该看什么、缺什么验证」。不荐股、不编数字。每次 AI 审视自动归档。
        </p>
      </div>

      <div style={{ background: "var(--bg-soft)", border: "1px solid var(--border)", borderRadius: 10, padding: "18px 20px", marginBottom: 8 }}>
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "end" }}>
          <div>
            <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 4 }}>代码 *</label>
            <input className="vi-in" value={ticker} onChange={(e) => setTicker(e.target.value)} placeholder="COST" style={{ width: 120 }} onKeyDown={(e) => e.key === "Enter" && !e.nativeEvent.isComposing && go()} />
          </div>
          <div>
            <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 4 }}>名称</label>
            <input className="vi-in" value={name} onChange={(e) => setName(e.target.value)} placeholder="Costco" style={{ width: 140 }} onKeyDown={(e) => e.key === "Enter" && !e.nativeEvent.isComposing && go()} />
          </div>
          <div>
            <label style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 4 }}>市场</label>
            <select className="vi-in" value={market} onChange={(e) => setMarket(e.target.value)}>
              {MARKETS.map((mk) => <option key={mk}>{mk}</option>)}
            </select>
          </div>
          <button className="btn btn-primary" onClick={go} disabled={dashLoading}>📊 分析</button>
        </div>
        {holdings.length > 0 && (
          <div style={{ marginTop: 12, fontSize: 13, color: "var(--muted)" }}>
            从持仓快速分析：
            {holdings.map((h, i) => (
              <button key={i} className="btn btn-ghost btn-sm" style={{ margin: 2 }} onClick={() => quick(h)}>{h.ticker}</button>
            ))}
          </div>
        )}
      </div>

      {dashLoading && !snap && <div className="ca-skel">📊 正在拉取 {cur.current?.ticker} 的真实数据…</div>}

      {snap && (
        <div className="ca-dash">
          <div className="ca-head2">
            <h2>{p?.name || snap.ticker}</h2>
            <span className="tick">{snap.ticker} · {snap.market}</span>
            {q?.price != null && (
              <span className="px">
                {fmtPx(q.price, ccy)}
                {q.change_pct != null && (
                  <span className={"chg " + (q.change_pct >= 0 ? "up" : "down")}>
                    {" "}{q.change_pct >= 0 ? "▲" : "▼"} {Math.abs(q.change_pct).toFixed(2)}%
                  </span>
                )}
              </span>
            )}
          </div>
          {(p?.sector || p?.industry || p?.exchange) && (
            <div className="ca-sub">
              {[p?.sector, p?.industry, p?.exchange].filter(Boolean).join(" · ")}
              {p?.employees ? <> <span className="dot">·</span>员工 {Number(p.employees).toLocaleString()}</> : null}
              {p?.website ? <> <span className="dot">·</span><a href={p.website} target="_blank" rel="noopener noreferrer" style={{ color: "var(--muted)" }}>官网↗</a></> : null}
            </div>
          )}
          <div className="ca-fresh">
            {snap.as_of && <span>数据更新于 {relTime(snap.as_of)}{snap._cached ? "（缓存）" : "（刚拉取）"}</span>}
            <button className="ca-refresh" disabled={dashLoading} onClick={() => cur.current && loadDashboard(cur.current.ticker, cur.current.name, cur.current.market, true)}>
              🔄 {dashLoading ? "刷新中…" : "刷新"}
            </button>
          </div>
          {snap.warnings && snap.warnings.length > 0 && <div className="ca-note">⚠️ {snap.warnings.join("；")}</div>}

          <div className="ca-tiles">
            <Tile k="市值" v={fmtMoney(q?.market_cap, ccy)} />
            <Tile k="P/E (TTM)" v={fmtX(m?.pe)} sub={m?.forward_pe != null ? "前瞻 " + fmtX(m.forward_pe) : undefined} />
            <Tile k="P/B" v={fmtX(m?.pb)} />
            <Tile k="P/S" v={fmtX(m?.ps)} />
            <Tile k="ROE" v={fmtPct(m?.roe)} />
            <Tile k="净利率" v={fmtPct(m?.net_margin)} />
            <Tile k="毛利率" v={fmtPct(m?.gross_margin)} />
            <Tile k="股息率" v={fmtPct(m?.dividend_yield)} />
            <Tile k="负债/权益" v={m?.debt_to_equity != null ? m.debt_to_equity.toFixed(0) + "%" : null} />
            <Tile k="营收增速" v={fmtPct(m?.revenue_growth)} />
            <Tile k="估值历史分位" v={valPctTile} sub={valPctSub} />
            <Tile k="52周区间" v={range} />
          </div>

          <div className="ca-panels">
            <div className="ca-panel">
              <h3>🏥 财务健康速览</h3>
              <p className="hint">五维 0–100 评分（越大越健康）。学习用启发式速览，不是买卖信号——高分仍要回原文核对。</p>
              {radar ? <EChart option={radar} /> : <div className="ca-skel">数据不足，无法评分</div>}
            </div>
            <div className="ca-panel">
              <h3>📈 营收 · 利润 · 利润率</h3>
              <p className="hint">柱=营收/净利润（左轴），线=净利率（右轴）。看趋势是否持续、利润率是否被侵蚀。</p>
              {trend ? <EChart option={trend} /> : <div className="ca-skel">暂无财报数据</div>}
            </div>
          </div>

          {snap.valuation_signals?.tools && snap.valuation_signals.tools.length > 0 && (
            <div className="ca-panel ca-consensus">
              <div style={{ display: "flex", alignItems: "baseline", gap: 10, flexWrap: "wrap" }}>
                <h3 style={{ margin: 0 }}>🎯 估值共识（四工具）· 便宜 {snap.valuation_signals.cheap_count}/{snap.valuation_signals.scored_count} 票</h3>
                <span className={"ca-deep " + (snap.valuation_signals.deep_research ? "yes" : "no")}>
                  {snap.valuation_signals.deep_research ? "≥2 票 → 可进深度研究" : "<2 票 → 暂不值得深研"}
                </span>
              </div>
              <p className="hint">先量出市场共识（它在赌什么），再去三支柱里找「真实可能偏离共识」的非共识点。</p>
              {snap.valuation_signals.reverse_dcf?.implied_growth != null && (
                <div className="ca-bet">
                  ★ 市场在赌什么：当前价隐含未来年增长 <b>≈ {(snap.valuation_signals.reverse_dcf.implied_growth * 100).toFixed(1)}%</b>
                  （历史营收 CAGR {pcStr(snap.valuation_signals.reverse_dcf.hist_rev_cagr)}，EPS CAGR {pcStr(snap.valuation_signals.reverse_dcf.hist_eps_cagr)}）
                </div>
              )}
              <div className="ca-tools">
                {snap.valuation_signals.tools.map((t, i) => (
                  <div className="ca-tool" key={i}>
                    <div className="tn">{t.name} <span className={"ca-verdict " + verdictCls(t.verdict)}>{t.verdict}</span></div>
                    <div className="td">{t.detail || "—"}</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 同行对比 — async (slower) */}
          {(peersLoading || peers) && (
            <div className="ca-panel ca-consensus">
              <div style={{ display: "flex", alignItems: "baseline", gap: 10, flexWrap: "wrap" }}>
                <h3 style={{ margin: 0 }}>🏟️ 同行对比{peers?.industry ? `（${peers.industry}）` : ""}</h3>
                {peers?.mispricing && <span className={"ca-verdict " + mispCls(peers.mispricing)}>{peers.mispricing}</span>}
              </div>
              <p className="hint">在同行里找错价：比同行便宜但质量更高 = 潜在错杀。补全四工具③（EV/EBIT 同行裁决）。</p>
              {peersLoading && !peers && <div className="ca-skel" style={{ textAlign: "left", padding: "10px 0" }}>同行数据加载中…（较慢，约 10–20 秒）</div>}
              {peers && peers.rows.length > 0 && (
                <>
                  <div className="ca-bet">四工具③ EV/EBIT 同行裁决：<b>{peers.ev_ebit_verdict}</b></div>
                  <div style={{ overflowX: "auto" }}>
                    <table className="ca-peers">
                      <thead>
                        <tr><th>代码</th><th>市值</th><th>P/E</th><th>EV/EBITDA</th><th>ROE</th><th>毛利率</th><th>净利率</th><th>营收增速</th></tr>
                      </thead>
                      <tbody>
                        {peers.rows.map((r, i) => (
                          <tr key={i} className={r.is_self ? "self" : ""}>
                            <td>{r.ticker}{r.is_self ? " ★" : ""}</td>
                            <td>{fmtMoney(r.market_cap, "USD") ?? "—"}</td>
                            <td>{fmtX(r.pe) ?? "—"}</td>
                            <td>{r.ev_ebitda != null ? r.ev_ebitda + "×" : "—"}</td>
                            <td>{fmtPct(r.roe) ?? "—"}</td>
                            <td>{fmtPct(r.gross_margin) ?? "—"}</td>
                            <td>{fmtPct(r.net_margin) ?? "—"}</td>
                            <td>{fmtPct(r.revenue_growth) ?? "—"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <p className="hint" style={{ marginTop: 10 }}>
                    ★行 = 本公司在同行中的百分位：估值 P/E {pctChip(peers.percentiles.pe)} · EV/EBITDA {pctChip(peers.percentiles.ev_ebitda)}（低=比同行便宜）；
                    质量 ROE {pctChip(peers.percentiles.roe)} · 净利率 {pctChip(peers.percentiles.net_margin)}（高=比同行好）
                  </p>
                </>
              )}
              {peers && peers.rows.length === 0 && (
                <div className="ca-skel" style={{ textAlign: "left", padding: "10px 0" }}>
                  {peers.warnings?.[0] || "暂无同行数据"}
                </div>
              )}
            </div>
          )}

          {/* 盈余质量 / 资金传导取证 */}
          {snap.quality_signals && (snap.quality_signals.cash_conversion || (snap.quality_signals.red_flags?.length ?? 0) > 0) && (
            <div className="ca-panel ca-consensus">
              <div style={{ display: "flex", alignItems: "baseline", gap: 10, flexWrap: "wrap" }}>
                <h3 style={{ margin: 0 }}>🩺 盈余质量 / 资金传导取证</h3>
                <span className={"ca-verdict " + ((snap.quality_signals.flag_count ?? 0) > 0 ? "rich" : "cheap")}>
                  红旗命中 {snap.quality_signals.flag_count ?? 0}
                </span>
              </div>
              <p className="hint">利润是不是真金白银、钱有没有越投越不值、有没有价值陷阱红旗——这些决定「便宜得有理」还是「价值陷阱」。</p>
              <div className="ca-tools" style={{ marginBottom: 10 }}>
                {snap.quality_signals.cash_conversion?.cum_fcf_ni != null && (
                  <div className="ca-tool">
                    <div className="tn">利润含金量</div>
                    <div className="td">累计 FCF/净利 = {snap.quality_signals.cash_conversion.cum_fcf_ni}（{snap.quality_signals.cash_conversion.verdict}）</div>
                  </div>
                )}
                {snap.quality_signals.incremental_roic?.incremental != null && (
                  <div className="ca-tool">
                    <div className="tn">增量 ROIC</div>
                    <div className="td">{pcStr(snap.quality_signals.incremental_roic.incremental)} vs 平均 {pcStr(snap.quality_signals.incremental_roic.avg_roic)}（{snap.quality_signals.incremental_roic.verdict}）</div>
                  </div>
                )}
                {snap.quality_signals.goodwill_ratio != null && (
                  <div className="ca-tool"><div className="tn">商誉 / 净资产</div><div className="td">{snap.quality_signals.goodwill_ratio}%</div></div>
                )}
                {snap.quality_signals.payout_ratio != null && (
                  <div className="ca-tool"><div className="tn">派息率</div><div className="td">{snap.quality_signals.payout_ratio}%</div></div>
                )}
              </div>
              {(snap.quality_signals.red_flags?.length ?? 0) > 0 && (
                <div>
                  {snap.quality_signals.red_flags!.map((f, i) => (
                    <div key={i} className="ca-flag">
                      <span className={"ca-verdict " + (f.hit ? "rich" : "na")}>{f.hit ? "🚩 命中" : "✓ 未中"}</span>
                      <span className="fn">{f.name}</span>
                      <span className="fd">{f.detail}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* 历史镜像 — 盈利周期位置 */}
          {snap.history_position?.metrics && snap.history_position.metrics.length > 0 && (
            <div className="ca-panel ca-consensus">
              <h3 style={{ margin: 0 }}>📜 历史镜像 · 盈利周期位置（{snap.history_position.span}）</h3>
              <p className="hint">当前指标在自己历史区间的位置（0%=历史最低，100%=历史最高）。市场是否把当前的峰值/谷值当常态外推？</p>
              {snap.history_position.metrics.map((m, i) => (
                <div className="ca-posrow" key={i}>
                  <span className="pn">{m.name}</span>
                  <span className="pv">{m.current}{m.unit}</span>
                  <div className="ca-postrack" title={`区间 ${m.min}~${m.max}，均值 ${m.avg}`}>
                    <div className="ca-posfill" style={{ width: m.position + "%" }} />
                  </div>
                  <span className="pr">{m.min}~{m.max}{m.unit}</span>
                  <span className={"ca-verdict " + (m.position >= 80 ? "rich" : m.position <= 20 ? "cheap" : "fair")}>{m.position}% · {m.state}</span>
                </div>
              ))}
              {snap.history_position.note && <div className="ca-bet" style={{ marginTop: 10 }}>★ {snap.history_position.note}</div>}
            </div>
          )}

          {/* 宏观资金传导 */}
          {snap.macro_signal?.note && (
            <div className="ca-panel ca-consensus">
              <div style={{ display: "flex", alignItems: "baseline", gap: 10, flexWrap: "wrap" }}>
                <h3 style={{ margin: 0 }}>🌐 宏观资金传导</h3>
                <span className={"ca-verdict " + (snap.macro_signal.sensitivity?.score === "高" ? "rich" : snap.macro_signal.sensitivity?.score === "低" ? "cheap" : "fair")}>
                  利率敏感度 {snap.macro_signal.sensitivity?.score ?? "—"}
                </span>
              </div>
              <p className="hint">利率/流动性/政策 → 行业 → 个股。环境（市场级）× 该公司的传导敏感度（杠杆/久期）。</p>
              <div className="ca-tiles" style={{ marginBottom: 10 }}>
                {snap.macro_signal.env?.ten_year != null && (
                  <Tile k="10Y 国债" v={snap.macro_signal.env.ten_year + "%"} sub={snap.macro_signal.env.rate_trend ? "近一年" + snap.macro_signal.env.rate_trend : undefined} />
                )}
                {snap.macro_signal.env?.curve_state && (
                  <Tile k="收益率曲线" v={snap.macro_signal.env.curve_state} sub={snap.macro_signal.env.curve_slope != null ? "10Y−短端 " + snap.macro_signal.env.curve_slope + "pp" : undefined} />
                )}
                {snap.macro_signal.env?.lpr_1y != null && <Tile k="1年期 LPR" v={snap.macro_signal.env.lpr_1y + "%"} />}
                {snap.macro_signal.env?.short_rate != null && <Tile k="短端利率" v={snap.macro_signal.env.short_rate + "%"} />}
              </div>
              <div className="ca-bet">★ {snap.macro_signal.note}</div>
            </div>
          )}

          <div className="ca-panel" style={{ marginBottom: 14 }}>
            <h3>💹 价格走势（近 5 年 · 月）</h3>
            <p className="hint">仅供感受波动与位置；价值投资看的是生意与估值，不是图形。</p>
            {price ? <EChart option={price} height={300} /> : <div className="ca-skel">暂无价格数据</div>}
          </div>

          <div className="ca-ai">
            <div className="head">
              <h3>🤖 让 hermes 按方法论审视</h3>
              <span className="sub">基于上面的真实数据，给出 第一性原理 / 资金传导 / 历史镜像 + 该补什么验证</span>
              <button className="btn btn-primary btn-sm" style={{ marginLeft: "auto" }} onClick={startAI} disabled={aiBusy}>开始 AI 审视</button>
              <span className={"status " + aiSt.cls}>{aiSt.msg}</span>
            </div>
            {report?.report && <div style={{ marginTop: 14 }}><Markdown>{report.report}</Markdown></div>}
          </div>

          <div className="ca-panel">
            <div className="ca-feed">
              <div>
                <h3>📄 一手文件（{isCN ? "巨潮公告" : "SEC"}）</h3>
                <p className="hint">{isCN ? "价值投资优先看原文：年报/季报、分红/回购、股东会决议等官方公告（巨潮资讯）。" : "价值投资优先看原文：10-K/10-Q 财报、8-K 重大事件、13F 机构持仓。"}</p>
                {news?.filings && news.filings.length > 0 ? (
                  news.filings.map((it, i) => <FeedItem key={i} it={it} />)
                ) : (
                  <div className="ca-skel" style={{ textAlign: "left", padding: "10px 0" }}>暂无一手文件（未匹配到该公司，或暂未接入该市场）</div>
                )}
              </div>
              <div>
                <h3>📰 新闻消息流</h3>
                <p className="hint">辅助了解市场叙事，别被标题带节奏。</p>
                {news?.news && news.news.length > 0 ? (
                  news.news.map((it, i) => <FeedItem key={i} it={it} />)
                ) : (
                  <div className="ca-skel" style={{ textAlign: "left", padding: "10px 0" }}>暂无新闻</div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      <h2 style={{ fontSize: 17, margin: "36px 0 12px", borderBottom: "1px solid var(--border)", paddingBottom: 8 }}>我的公司库（归档）</h2>
      {archive.length === 0 ? (
        <p style={{ color: "var(--muted)", fontSize: 14 }}>还没有 AI 审视记录。输入代码点「分析」看数据，再点「开始 AI 审视」。</p>
      ) : (
        <div className="vi-grid">
          {archive.map((a, i) => (
            <motion.div
              key={a.id}
              className="vi-card hoverable"
              style={{ cursor: "pointer" }}
              onClick={() => openArchive(a)}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: Math.min(i * 0.04, 0.3) }}
            >
              <h3>
                {a.ticker}{" "}
                {a.company_name && <span style={{ color: "var(--muted)", fontSize: 13, fontWeight: 400 }}>{a.company_name}</span>}
              </h3>
              <p>{a.market || ""} · {a.status === "done" ? "已完成" : a.status === "error" ? "失败/超时" : a.status}</p>
              <div className="meta">{a.created_at ? new Date(a.created_at).toLocaleString("zh-CN") : ""}</div>
            </motion.div>
          ))}
        </div>
      )}
    </>
  );
}
