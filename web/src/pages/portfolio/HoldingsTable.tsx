const MARKETS = ["美股", "A股", "港股", "加密"];

export interface Row {
  _id: number;
  market: string;
  ticker: string;
  name: string;
  buy_date: string;
  cost: string;
  position_pct: string;
  note: string;
}

export function HoldingsTable({
  rows, onChange, onDelete, onAnalyze,
}: {
  rows: Row[];
  onChange: (id: number, field: keyof Row, value: string) => void;
  onDelete: (id: number) => void;
  onAnalyze: (r: Row) => void;
}) {
  return (
    <div className="table-wrap">
      <table className="holdings-table">
        <thead>
          <tr>
            <th style={{ width: 90 }}>市场</th>
            <th style={{ width: 110 }}>代码</th>
            <th style={{ width: 140 }}>名称</th>
            <th style={{ width: 130 }}>买入日期</th>
            <th style={{ width: 110 }}>成本价</th>
            <th style={{ width: 90 }}>仓位%</th>
            <th>备注 / thesis 一句话</th>
            <th style={{ width: 74 }}></th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r._id}>
              <td>
                <select value={r.market} onChange={(e) => onChange(r._id, "market", e.target.value)}>
                  {MARKETS.map((m) => <option key={m}>{m}</option>)}
                </select>
              </td>
              <td><input value={r.ticker} onChange={(e) => onChange(r._id, "ticker", e.target.value)} placeholder="COST" /></td>
              <td><input value={r.name} onChange={(e) => onChange(r._id, "name", e.target.value)} placeholder="Costco" /></td>
              <td><input type="date" value={r.buy_date} onChange={(e) => onChange(r._id, "buy_date", e.target.value)} /></td>
              <td className="num"><input type="number" step="any" value={r.cost} onChange={(e) => onChange(r._id, "cost", e.target.value)} placeholder="0.00" /></td>
              <td className="num"><input type="number" step="any" value={r.position_pct} onChange={(e) => onChange(r._id, "position_pct", e.target.value)} placeholder="0" /></td>
              <td><input value={r.note} onChange={(e) => onChange(r._id, "note", e.target.value)} placeholder="为什么买 / thesis" /></td>
              <td style={{ whiteSpace: "nowrap" }}>
                <button className="anz" title="分析这家公司" onClick={() => onAnalyze(r)}>📊</button>
                <button className="del" title="删除" onClick={() => onDelete(r._id)}>✕</button>
              </td>
            </tr>
          ))}
          {rows.length === 0 && (
            <tr><td colSpan={8} className="empty">还没有持仓 — 点「+ 添加一行」开始记录。</td></tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
