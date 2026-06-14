import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiGet, apiPut } from "../lib/api";
import { useMe } from "../lib/hooks";
import type { Holding } from "../lib/types";
import { HoldingsTable, type Row } from "./portfolio/HoldingsTable";
import { PhotoImport, type NewRow } from "./portfolio/PhotoImport";
import { ExchangeImport } from "./portfolio/ExchangeImport";
import { Report } from "./portfolio/Report";

let rowId = 1;
function toRow(h: Partial<Holding> & Partial<NewRow>): Row {
  return {
    _id: rowId++,
    market: h.market || "美股",
    ticker: h.ticker || "",
    name: h.name || "",
    buy_date: (h as Holding).buy_date || "",
    cost: (h as Holding).cost != null ? String((h as Holding).cost) : "",
    position_pct: (h as Holding).position_pct != null ? String((h as Holding).position_pct) : "",
    note: h.note || "",
  };
}

export default function Portfolio() {
  const user = useMe();
  const nav = useNavigate();
  const [rows, setRows] = useState<Row[]>([]);
  const [st, setSt] = useState<{ msg: string; cls: string }>({ msg: "", cls: "" });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (user === null) nav("/login", { replace: true });
  }, [user, nav]);

  async function load() {
    const r = await apiGet<{ holdings: Holding[]; updated_at?: string }>("/api/holdings");
    setRows((r.data?.holdings ?? []).map(toRow));
    if (r.data?.updated_at) setSt({ msg: "上次保存 · " + new Date(r.data.updated_at).toLocaleString("zh-CN"), cls: "" });
  }
  useEffect(() => {
    if (user) load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user]);

  function change(id: number, field: keyof Row, value: string) {
    setRows((rs) => rs.map((r) => (r._id === id ? { ...r, [field]: value } : r)));
  }
  function del(id: number) {
    setRows((rs) => rs.filter((r) => r._id !== id));
  }
  function addRow() {
    setRows((rs) => [...rs, toRow({})]);
  }
  function addRows(newRows: NewRow[]) {
    setRows((rs) => [...rs, ...newRows.map(toRow)]);
  }
  function analyze(r: Row) {
    nav("/analyze?ticker=" + encodeURIComponent(r.ticker) + "&name=" + encodeURIComponent(r.name) + "&market=" + encodeURIComponent(r.market));
  }

  async function save() {
    setSaving(true);
    setSt({ msg: "保存中…", cls: "" });
    const holdings = rows
      .filter((r) => r.ticker.trim() || r.name.trim() || r.note.trim())
      .map((r) => ({
        market: r.market,
        ticker: r.ticker.trim(),
        name: r.name.trim(),
        buy_date: r.buy_date || "",
        cost: r.cost === "" ? null : Number(r.cost),
        position_pct: r.position_pct === "" ? null : Number(r.position_pct),
        note: r.note.trim(),
      }));
    const r = await apiPut<{ updated_at?: string; error?: string }>("/api/holdings", { holdings });
    setSaving(false);
    if (r.status === 401) {
      nav("/login", { replace: true });
      return;
    }
    if (r.ok) setSt({ msg: "已保存 · " + new Date(r.data?.updated_at || "").toLocaleString("zh-CN"), cls: "ok" });
    else setSt({ msg: "保存失败：" + (r.data?.error || r.status), cls: "err" });
  }

  async function logout() {
    try {
      await fetch("/api/logout", { method: "POST", credentials: "same-origin" });
    } catch {
      /* ignore */
    }
    nav("/login", { replace: true });
  }

  return (
    <>
      <div className="app-head" style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", flexWrap: "wrap", gap: 12 }}>
        <div>
          <div className="eyebrow">Portfolio</div>
          <h1>持仓输入</h1>
          <p>记录「我现在买了哪些」。轻量版——代码 / 市场 / 成本价 / 仓位 / 备注。这是整个系统的「输入端口」。</p>
        </div>
        <button className="btn btn-ghost btn-sm" onClick={logout}>退出</button>
      </div>
      <div className="privacy">🔒 <b>私有数据</b>：你的持仓存在服务器、按访问码隔离，只有你能看到。</div>

      <HoldingsTable rows={rows} onChange={change} onDelete={del} onAnalyze={analyze} />
      <div style={{ display: "flex", gap: 12, alignItems: "center", marginTop: 18, flexWrap: "wrap" }}>
        <button className="btn btn-ghost" onClick={addRow}>+ 添加一行</button>
        <button className="btn btn-primary" onClick={save} disabled={saving}>保存</button>
        <span className={"status " + st.cls} style={{ marginLeft: "auto" }}>{st.msg}</span>
      </div>

      <PhotoImport onAdd={addRows} />
      <ExchangeImport onImported={load} />
      <Report />
    </>
  );
}
