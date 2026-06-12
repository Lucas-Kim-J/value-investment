import { useEffect, useRef, useState } from "react";
import { apiGet, apiPost } from "../../lib/api";
import type { ReportState } from "../../lib/types";
import { Markdown } from "../../shell/Markdown";

export function Report() {
  const [report, setReport] = useState("");
  const [meta, setMeta] = useState("");
  const [canPush, setCanPush] = useState(false);
  const [st, setSt] = useState<{ msg: string; cls: string }>({ msg: "", cls: "" });
  const [busy, setBusy] = useState(false);
  const [pushing, setPushing] = useState(false);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; };
  }, []);

  function show(d: ReportState) {
    if (!mounted.current) return;
    setReport(d.report || "");
    setMeta(d.generated_at ? "生成于 " + new Date(d.generated_at).toLocaleString("zh-CN") : "");
    setCanPush(!!d.can_push);
    setSt({ msg: "", cls: "ok" });
  }

  async function poll() {
    const t0 = Date.now();
    while (mounted.current && Date.now() - t0 < 200000) {
      await new Promise((r) => setTimeout(r, 3000));
      if (!mounted.current) return;
      let d: ReportState | null = null;
      try {
        d = (await apiGet<ReportState>("/api/report")).data;
      } catch {
        continue;
      }
      if (!d) continue;
      if (d.status === "done") { show(d); setBusy(false); return; }
      if (d.status === "error") { setSt({ msg: "生成失败：" + (d.error || "未知"), cls: "err" }); setBusy(false); return; }
      setSt({ msg: "生成中… " + Math.round((Date.now() - t0) / 1000) + "s（hermes 正按方法论审视持仓）", cls: "" });
    }
    if (mounted.current) { setSt({ msg: "超时，请重试", cls: "err" }); setBusy(false); }
  }

  async function gen() {
    setBusy(true);
    setReport("");
    setSt({ msg: "生成中…（约 30-90 秒）", cls: "" });
    const r = await apiPost<{ error?: string }>("/api/report");
    if (!r.ok) {
      setSt({ msg: "启动失败：" + (r.data?.error || r.status), cls: "err" });
      setBusy(false);
      return;
    }
    poll();
  }

  async function push() {
    setPushing(true);
    setSt({ msg: "推送中…", cls: "" });
    const r = await apiPost<{ error?: string }>("/api/report/push");
    setPushing(false);
    setSt({ msg: r.ok ? "已发到飞书 ✓" : "推送失败：" + (r.data?.error || r.status), cls: r.ok ? "ok" : "err" });
  }

  useEffect(() => {
    apiGet<ReportState>("/api/report").then((r) => {
      const d = r.data;
      if (d?.status === "done" && d.report) show(d);
      else if (d?.status === "running") {
        setBusy(true);
        setSt({ msg: "生成中…", cls: "" });
        poll();
      }
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div style={{ marginTop: 40, paddingTop: 24, borderTop: "1px solid var(--border)" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
        <h2 style={{ fontSize: 20, margin: 0 }}>规范报告</h2>
        <div style={{ display: "flex", gap: 10 }}>
          {canPush && <button className="btn btn-ghost" onClick={push} disabled={pushing}>发到飞书</button>}
          <button className="btn btn-primary" onClick={gen} disabled={busy}>📝 生成规范报告</button>
        </div>
      </div>
      <p style={{ color: "var(--muted)", fontSize: 13, margin: "8px 0 14px", lineHeight: 1.55 }}>
        基于你当前持仓 + 方法论，由服务器上的 hermes 生成（首次约 30-90 秒）。不给买卖建议，只用方法论视角审视你的流程与纪律——哪些仓位缺 thesis / 缺估值 / 没过 Pabrai 三问。
      </p>
      <div className={"status " + st.cls}>{st.msg || meta}</div>
      {report && <Markdown>{report}</Markdown>}
    </div>
  );
}
