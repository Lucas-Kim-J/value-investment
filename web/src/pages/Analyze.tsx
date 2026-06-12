import { useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { motion } from "framer-motion";
import { apiGet, apiPost } from "../lib/api";
import { useMe } from "../lib/hooks";
import type { AnalysisDetail, AnalysisItem, Holding } from "../lib/types";
import { Markdown } from "../shell/Markdown";

const MARKETS = ["美股", "A股", "港股", "加密"];

export default function Analyze() {
  const user = useMe();
  const nav = useNavigate();
  const [params] = useSearchParams();

  const [ticker, setTicker] = useState("");
  const [name, setName] = useState("");
  const [market, setMarket] = useState("美股");
  const [st, setSt] = useState<{ msg: string; cls: string }>({ msg: "", cls: "" });
  const [busy, setBusy] = useState(false);
  const [pulse, setPulse] = useState(false);
  const [report, setReport] = useState<AnalysisDetail | null>(null);
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

  function showReport(d: AnalysisDetail) {
    if (!mounted.current) return;
    setReport(d);
    setSt({
      msg: (d.ticker || "") + " 分析完成 · " + (d.generated_at ? new Date(d.generated_at).toLocaleString("zh-CN") : ""),
      cls: "ok",
    });
  }

  async function poll(id: number) {
    const t0 = Date.now();
    while (mounted.current && Date.now() - t0 < 200000) {
      await new Promise((r) => setTimeout(r, 3000));
      if (!mounted.current) return;
      let d: AnalysisDetail | null = null;
      try {
        d = (await apiGet<AnalysisDetail>("/api/analyses/" + id)).data;
      } catch {
        continue;
      }
      if (!d) continue;
      if (d.status === "done") { showReport(d); return; }
      if (d.status === "error") { setSt({ msg: "分析失败：" + (d.error || "未知"), cls: "err" }); return; }
      setSt({ msg: "分析中… " + Math.round((Date.now() - t0) / 1000) + "s", cls: "" });
    }
    if (mounted.current) setSt({ msg: "超时，请重试", cls: "err" });
  }

  async function analyze(t: string, n: string, m: string) {
    setBusy(true);
    setReport(null);
    setSt({ msg: "已提交，hermes 正按你的学习阶段审视…（约 30-90 秒）", cls: "" });
    try {
      const r = await apiPost<{ id: number; error?: string }>("/api/analyses", { ticker: t, name: n, market: m });
      if (r.status === 401) { nav("/login", { replace: true }); return; }
      if (!r.ok || !r.data?.id) {
        setSt({ msg: "启动失败：" + (r.data?.error || r.status), cls: "err" });
        setBusy(false);
        return;
      }
      await poll(r.data.id);
    } catch (e) {
      setSt({ msg: "网络错误：" + (e as Error).message, cls: "err" });
    }
    // mirror vanilla: reached only on success/network-error fall-through, NOT on the 401 / startup-failure early returns
    if (mounted.current) setBusy(false);
    loadArchive();
  }

  function go() {
    const t = ticker.trim();
    if (!t) { setSt({ msg: "请输入公司代码", cls: "err" }); return; }
    setPulse(false);
    analyze(t, name.trim(), market);
  }

  function quick(h: Holding) {
    setTicker(h.ticker);
    setName(h.name || "");
    if (h.market) setMarket(h.market);
    analyze(h.ticker, h.name || "", h.market || "");
  }

  async function loadArchive() {
    const r = await apiGet<{ items: AnalysisItem[] }>("/api/analyses");
    if (mounted.current) setArchive(r.data?.items ?? []);
  }

  async function openArchive(id: number) {
    const r = await apiGet<AnalysisDetail>("/api/analyses/" + id);
    const d = r.data;
    if (d && d.status === "done") {
      showReport(d);
      window.scrollTo({ top: 0, behavior: "smooth" });
    } else if (d && d.status === "running") {
      setSt({ msg: "这份还在生成中…", cls: "" });
      poll(id);
    } else setSt({ msg: "这份分析没有内容（可能失败）", cls: "err" });
  }

  // initial load: holdings (quick buttons) + archive + query-string prefill
  useEffect(() => {
    if (!user) return;
    apiGet<{ holdings: Holding[] }>("/api/holdings").then((r) => {
      if (mounted.current) setHoldings(r.data?.holdings ?? []);
    });
    loadArchive();
    const t = params.get("ticker");
    if (t) {
      setTicker(t);
      if (params.get("name")) setName(params.get("name")!);
      if (params.get("market")) setMarket(params.get("market")!);
      setPulse(true);
      setSt({ msg: "已带入 " + t + "，点「一键分析」开始", cls: "" });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user]);

  return (
    <>
      <div className="app-head">
        <div className="eyebrow">Company Analysis</div>
        <h1>公司分析</h1>
        <p>
          一键让 hermes 按价值投资方法论审视一家公司——并<strong>按你的学习阶段</strong>调整详略（新手多解释，进阶更犀利）。不荐股、不编数字，只帮你看「该看什么、缺什么验证」。每次分析自动归档，可回看演进。
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
              {MARKETS.map((m) => <option key={m}>{m}</option>)}
            </select>
          </div>
          <button className={"btn btn-primary" + (pulse ? " btn-pulse" : "")} onClick={go} disabled={busy}>📝 一键分析</button>
          <span className={"status " + st.cls}>{st.msg}</span>
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

      {report && (
        <div style={{ marginTop: 20 }}>
          <div style={{ background: "var(--bg-soft)", border: "1px solid var(--border)", borderRadius: 10, padding: "20px 24px" }}>
            <div style={{ color: "var(--muted)", fontSize: 13, marginBottom: 10 }}>
              {report.ticker} {report.company_name || ""} · {report.market || ""}
            </div>
            <Markdown>{report.report || ""}</Markdown>
          </div>
        </div>
      )}

      <h2 style={{ fontSize: 17, margin: "36px 0 12px", borderBottom: "1px solid var(--border)", paddingBottom: 8 }}>我的公司库（归档）</h2>
      {archive.length === 0 ? (
        <p style={{ color: "var(--muted)", fontSize: 14 }}>还没有分析记录。在上面输入一个公司代码，点「一键分析」。</p>
      ) : (
        <div className="vi-grid">
          {archive.map((a, i) => (
            <motion.div
              key={a.id}
              className="vi-card hoverable"
              style={{ cursor: "pointer" }}
              onClick={() => openArchive(a.id)}
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
