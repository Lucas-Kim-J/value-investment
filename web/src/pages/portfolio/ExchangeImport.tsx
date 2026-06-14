import { useEffect, useState } from "react";
import { apiDelete, apiGet, apiPost } from "../../lib/api";
import type { ExchangeKeyInfo, ExchangeSnapshot } from "../../lib/types";

const num = (n: number) => n.toLocaleString(undefined, { maximumFractionDigits: 6 });

function SnapshotView({
  snap, manual, setManual, onSaveManual, manualSt, onImport, impSt,
}: {
  snap: ExchangeSnapshot;
  manual: string;
  setManual: (v: string) => void;
  onSaveManual: () => void;
  manualSt: { msg: string; cls: string };
  onImport: () => void;
  impSt: { msg: string; cls: string };
}) {
  // mirror vanilla: hide sub-$0.01 dust from the spot table
  const spot = (snap.spot || []).filter((x) => x.usd >= 0.01);
  return (
    <>
      <div className="ex-total">总资产 ≈ <b>${snap.total_usdt}</b></div>
      {Object.keys(snap.by_account || {}).length > 0 && (
        <div className="ex-chips">
          {Object.entries(snap.by_account).map(([k, v]) => <span key={k} className="ex-chip">{k} ${v}</span>)}
        </div>
      )}
      {spot.length > 0 && (
        <>
          <div className="ex-section-h">现货</div>
          <table className="ex-snap-table">
            <thead><tr><th>币种</th><th style={{ textAlign: "right" }}>数量</th><th style={{ textAlign: "right" }}>≈USD</th></tr></thead>
            <tbody>{spot.map((x) => <tr key={x.coin}><td>{x.coin}</td><td style={{ textAlign: "right" }}>{num(x.amount)}</td><td style={{ textAlign: "right" }}>${x.usd}</td></tr>)}</tbody>
          </table>
        </>
      )}
      {snap.finance && snap.finance.length > 0 && (
        <>
          <div className="ex-section-h">理财</div>
          <table className="ex-snap-table">
            <thead><tr><th>币种</th><th>产品</th><th style={{ textAlign: "right" }}>数量</th><th style={{ textAlign: "right" }}>≈USD</th></tr></thead>
            <tbody>{snap.finance.map((x) => <tr key={x.coin}><td>{x.coin}</td><td style={{ color: "var(--muted)" }}>{x.product}</td><td style={{ textAlign: "right" }}>{num(x.amount)}</td><td style={{ textAlign: "right" }}>${x.usd}</td></tr>)}</tbody>
          </table>
        </>
      )}
      {snap.futures?.length > 0 && (
        <>
          <div className="ex-section-h">合约持仓</div>
          <table className="ex-snap-table">
            <thead><tr><th>合约</th><th style={{ textAlign: "right" }}>数量</th><th style={{ textAlign: "right" }}>价值</th><th style={{ textAlign: "right" }}>未实现盈亏</th></tr></thead>
            <tbody>{snap.futures.map((x) => <tr key={x.contract}><td>{x.contract}</td><td style={{ textAlign: "right" }}>{x.size}</td><td style={{ textAlign: "right" }}>${x.value}</td><td style={{ textAlign: "right", color: x.upnl >= 0 ? "var(--good)" : "var(--warn)" }}>{x.upnl >= 0 ? "+" : ""}{x.upnl}</td></tr>)}</tbody>
          </table>
        </>
      )}
      <div className="ex-section-h" title="Gate 公开 API 不提供 TradFi 股票账户，只能手填">TradFi 股票（API 拉不到 · 手填净值）</div>
      <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 14 }}>
        <input className="vi-in" type="number" step="any" min={0} value={manual} onChange={(e) => setManual(e.target.value)} placeholder="0" style={{ width: 120 }} />
        <span style={{ color: "var(--muted)", fontSize: 13 }}>USDT</span>
        <button className="btn btn-ghost btn-sm" onClick={onSaveManual}>保存并计入总额</button>
        <span className={"status " + manualSt.cls}>{manualSt.msg}</span>
      </div>
      <button className="btn btn-primary" onClick={onImport}>⬇ 导入到持仓表</button> <span className={"status " + impSt.cls}>{impSt.msg}</span>
    </>
  );
}

export function ExchangeImport({ onImported }: { onImported: () => void }) {
  const [keys, setKeys] = useState<ExchangeKeyInfo[]>([]);
  const [exchange, setExchange] = useState("gate");
  const [apiKey, setApiKey] = useState("");
  const [secret, setSecret] = useState("");
  const [addSt, setAddSt] = useState<{ msg: string; cls: string }>({ msg: "", cls: "" });
  const [adding, setAdding] = useState(false);
  const [snap, setSnap] = useState<{ id: number; data: ExchangeSnapshot } | null>(null);
  const [snapSt, setSnapSt] = useState("");
  const [impSt, setImpSt] = useState<{ msg: string; cls: string }>({ msg: "", cls: "" });
  const [manual, setManual] = useState("");
  const [manualSt, setManualSt] = useState<{ msg: string; cls: string }>({ msg: "", cls: "" });

  async function load() {
    const r = await apiGet<{ items: ExchangeKeyInfo[] }>("/api/exchange/keys");
    setKeys(r.data?.items ?? []);
  }
  useEffect(() => { load(); }, []);

  async function add() {
    if (!apiKey.trim() || !secret.trim()) {
      setAddSt({ msg: "请填 API Key 和 Secret", cls: "err" });
      return;
    }
    setAdding(true);
    setAddSt({ msg: "验证中…（会做一次只读拉取）", cls: "" });
    const r = await apiPost<{ ok: boolean; error?: string }>("/api/exchange/keys", { exchange, api_key: apiKey.trim(), api_secret: secret.trim() });
    setAdding(false);
    if (r.ok) {
      setAddSt({ msg: "已连接 ✓", cls: "ok" });
      setApiKey("");
      setSecret("");
      load();
    } else setAddSt({ msg: r.data?.error || "连接失败", cls: "err" });
  }

  async function sync(id: number) {
    setSnap(null);
    setImpSt({ msg: "", cls: "" });
    setManualSt({ msg: "", cls: "" });
    setSnapSt("同步中…（约 5-12 秒）");
    const r = await apiPost<{ snapshot: ExchangeSnapshot; error?: string }>("/api/exchange/keys/" + id + "/sync");
    setSnapSt("");
    if (!r.ok || !r.data?.snapshot) {
      setImpSt({ msg: r.data?.error || "同步失败", cls: "err" });
      return;
    }
    setSnap({ id, data: r.data.snapshot });
    setManual(r.data.snapshot.manual_usd ? String(r.data.snapshot.manual_usd) : "");
  }

  async function importToHoldings(id: number) {
    setImpSt({ msg: "导入中…", cls: "" });
    const r = await apiPost<{ added: number; error?: string }>("/api/exchange/keys/" + id + "/import");
    if (r.ok) {
      setImpSt({ msg: "已导入 " + (r.data?.added || 0) + " 个新币种 ✓（在上面的持仓表里）", cls: "ok" });
      onImported();
    } else setImpSt({ msg: r.data?.error || "失败", cls: "err" });
  }

  async function saveManual(id: number) {
    const v = parseFloat(manual) || 0;
    setManualSt({ msg: "保存中…", cls: "" });
    const r = await apiPost<{ ok: boolean; error?: string }>("/api/exchange/keys/" + id + "/manual", { usd: v });
    if (r.ok && snap) {
      const base = (snap.data.total_usdt || 0) - (snap.data.manual_usd || 0);
      setSnap({ id, data: { ...snap.data, manual_usd: v, total_usdt: Math.round((base + v) * 100) / 100 } });
      setManualSt({ msg: "已保存，已计入总额 ✓", cls: "ok" });
    } else setManualSt({ msg: r.data?.error || "失败", cls: "err" });
  }

  async function del(id: number) {
    if (!confirm("删除这个交易所连接？(不影响已导入的持仓)")) return;
    await apiDelete("/api/exchange/keys/" + id);
    setSnap(null);
    load();
  }

  return (
    <div className="ex-section">
      <h2>🔗 交易所导入（加密）</h2>
      <p className="ex-intro">连接交易所<strong>只读</strong> API，一键拉取你的加密持仓。secret 加密存服务器、绝不外泄，只做读操作。</p>
      {keys.map((k) => (
        <div key={k.id} className="ex-card">
          <span className="ex-name">{k.label || k.exchange}</span>
          <span className="ex-key">{k.key_masked}</span>
          <span className="sp" />
          <button className="btn btn-primary btn-sm" onClick={() => sync(k.id)}>🔄 同步</button>
          <button className="btn btn-ghost btn-sm" onClick={() => del(k.id)}>🗑</button>
        </div>
      ))}
      <details>
        <summary style={{ cursor: "pointer", color: "var(--accent)", fontSize: 14, fontWeight: 600, padding: "6px 0" }}>+ 连接一个交易所</summary>
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center", marginTop: 12 }}>
          <select className="vi-in" value={exchange} onChange={(e) => setExchange(e.target.value)}>
            <option value="gate">Gate.io</option>
            <option value="okx" disabled>OKX（即将支持）</option>
            <option value="binance" disabled>Binance（即将支持）</option>
            <option value="bybit" disabled>Bybit（即将支持）</option>
          </select>
          <input className="vi-in" value={apiKey} onChange={(e) => setApiKey(e.target.value)} placeholder="API Key" autoComplete="off" spellCheck={false} style={{ minWidth: 230, flex: 1 }} />
          <input className="vi-in" type="password" value={secret} onChange={(e) => setSecret(e.target.value)} placeholder="API Secret" autoComplete="off" spellCheck={false} style={{ minWidth: 230, flex: 1 }} />
          <button className="btn btn-primary" onClick={add} disabled={adding}>连接并验证</button>
          <span className={"status " + addSt.cls}>{addSt.msg}</span>
        </div>
        <p style={{ color: "var(--muted)", fontSize: 12.5, margin: "10px 0 0" }}>⚠️ 创建 key 时只勾选「只读 / 读取」（现货 / 合约 / 钱包 / 理财），<strong>不要开提现</strong>。</p>
      </details>
      {snapSt && <p className="status" style={{ marginTop: 14 }}>{snapSt}</p>}
      {snap && (
        <SnapshotView
          snap={snap.data}
          manual={manual}
          setManual={setManual}
          onSaveManual={() => saveManual(snap.id)}
          manualSt={manualSt}
          onImport={() => importToHoldings(snap.id)}
          impSt={impSt}
        />
      )}
    </div>
  );
}
