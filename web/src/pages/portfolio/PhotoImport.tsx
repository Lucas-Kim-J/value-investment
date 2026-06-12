import { useEffect, useRef, useState } from "react";
import type { ParsedHolding } from "../../lib/types";

export interface NewRow { market: string; ticker: string; name: string; note: string }

export function PhotoImport({ onAdd }: { onAdd: (rows: NewRow[]) => void }) {
  const [st, setSt] = useState<{ msg: string; cls: string }>({ msg: "", cls: "" });
  const [parsed, setParsed] = useState<ParsedHolding[] | null>(null);
  const [warnings, setWarnings] = useState<string[]>([]);
  const fileRef = useRef<HTMLInputElement>(null);
  const stRef = useRef<HTMLSpanElement>(null);

  async function parse(file: File) {
    setSt({ msg: "识别中…（hermes 读图，约 30-60 秒）", cls: "" });
    setParsed(null);
    stRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
    const fd = new FormData();
    fd.append("image", file);
    try {
      const r = await fetch("/api/holdings/parse-image", { method: "POST", credentials: "same-origin", body: fd });
      if (r.status === 401) {
        window.location.href = "/login";
        return;
      }
      const d = await r.json().catch(() => ({}));
      if (!r.ok) {
        setSt({ msg: d.error || "识别失败 " + r.status, cls: "err" });
        return;
      }
      setParsed(d.holdings || []);
      setWarnings(d.warnings || []);
      setSt({ msg: "识别完成 ✓ 核对后加入", cls: "ok" });
    } catch (e) {
      setSt({ msg: "网络错误：" + (e as Error).message, cls: "err" });
    }
  }

  useEffect(() => {
    const onPaste = (e: ClipboardEvent) => {
      const items = e.clipboardData?.items || [];
      for (const it of items) {
        if (it.type && it.type.indexOf("image") === 0) {
          const f = it.getAsFile();
          if (f) {
            e.preventDefault();
            parse(f);
          }
          return;
        }
      }
    };
    document.addEventListener("paste", onPaste);
    return () => document.removeEventListener("paste", onPaste);
  }, []);

  function doImport() {
    if (!parsed) return;
    const rows: NewRow[] = parsed.map((h) => ({
      market: h.market || "加密",
      ticker: (h.symbol || "").toUpperCase(),
      name: h.name || "",
      note:
        ((h.quantity != null ? h.quantity + " " : "") + (h.value_usd != null ? "≈$" + h.value_usd : "")).trim() +
        "（拍照识别）",
    }));
    onAdd(rows);
    setParsed(null);
    setSt({ msg: "已加入 " + rows.length + " 行——核对后点「保存」", cls: "ok" });
  }

  return (
    <div className="ex-section">
      <h2>📷 拍照 / 截图识别持仓</h2>
      <p className="ex-intro">
        上传任意账户的持仓截图（交易所 / 券商 / 钱包都行）—— hermes 自动读图识别成持仓，绕开所有 API 限制（比如 Gate 那个 API 拉不到的 TradFi 股票，截个图就进来了）。
      </p>
      <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
        <input
          ref={fileRef}
          type="file"
          accept="image/*"
          style={{ display: "none" }}
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) parse(f);
            e.target.value = "";
          }}
        />
        <button className="btn btn-primary" onClick={() => fileRef.current?.click()}>📷 选图 / 拍照</button>
        <span style={{ color: "var(--muted)", fontSize: 13 }}>
          或在本页直接 <kbd>⌘V</kbd> / <kbd>Ctrl+V</kbd> 粘贴截图
        </span>
        <span ref={stRef} className={"status " + st.cls}>{st.msg}</span>
      </div>
      {parsed && parsed.length > 0 && (
        <div style={{ marginTop: 14 }}>
          {warnings.length > 0 && <p className="status">⚠️ {warnings.join("；")}</p>}
          <table className="ex-snap-table">
            <thead>
              <tr><th>代码</th><th>市场</th><th style={{ textAlign: "right" }}>数量</th><th style={{ textAlign: "right" }}>≈USD</th></tr>
            </thead>
            <tbody>
              {parsed.map((h, i) => (
                <tr key={i}>
                  <td>{h.symbol}</td>
                  <td>{h.market}</td>
                  <td style={{ textAlign: "right" }}>{h.quantity ?? ""}</td>
                  <td style={{ textAlign: "right" }}>{h.value_usd != null ? "$" + h.value_usd : ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <button className="btn btn-primary" onClick={doImport}>⬇ 加入持仓表（可再编辑）</button>
        </div>
      )}
      {parsed && parsed.length === 0 && (
        <p className="status" style={{ marginTop: 10 }}>没认出持仓，换张更清晰、含币种和数量的截图试试。</p>
      )}
    </div>
  );
}
