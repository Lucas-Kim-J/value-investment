import { type FormEvent, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { apiPost, me } from "../lib/api";

export default function Login() {
  const nav = useNavigate();
  const [code, setCode] = useState("");
  const [msg, setMsg] = useState("");
  const [cls, setCls] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    me().then((u) => {
      if (u) nav("/portfolio", { replace: true });
    });
  }, [nav]);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!code.trim()) {
      setMsg("请输入访问码");
      setCls("err");
      return;
    }
    setBusy(true);
    setMsg("验证中…");
    setCls("");
    const r = await apiPost<{ ok: boolean; user: string; error?: string }>("/api/login", { code: code.trim() });
    if (r.ok && r.data?.ok) {
      nav("/portfolio", { replace: true });
    } else {
      setMsg(r.data?.error || "访问码无效");
      setCls("err");
      setBusy(false);
    }
  }

  return (
    <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", padding: 24 }}>
      <motion.div
        initial={{ opacity: 0, y: 12, scale: 0.98 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
        style={{
          width: "100%", maxWidth: 380, background: "var(--bg-soft)", border: "1px solid var(--border)",
          borderRadius: 14, padding: "34px 30px", boxShadow: "var(--shadow-2)",
        }}
      >
        <div style={{ color: "var(--muted)", fontSize: 12, textTransform: "uppercase", letterSpacing: ".14em", fontWeight: 600, marginBottom: 8 }}>
          Value Investing · 输入端口
        </div>
        <h1 style={{ fontSize: 23, margin: "0 0 6px" }}>🔒 访问码登录</h1>
        <p style={{ color: "var(--fg-soft)", fontSize: 14, margin: "0 0 24px", lineHeight: 1.5 }}>
          输入你的访问码进入私有输入端口。只读学习站无需登录。
        </p>
        <form onSubmit={submit} autoComplete="off">
          <label style={{ display: "block", fontSize: 13, color: "var(--muted)", marginBottom: 6, fontWeight: 600 }}>访问码</label>
          <input className="vi-in" type="password" value={code} onChange={(e) => setCode(e.target.value)} placeholder="••••••••" autoFocus style={{ width: "100%" }} />
          <button className="btn btn-primary" type="submit" disabled={busy} style={{ width: "100%", marginTop: 16 }}>登录</button>
        </form>
        <div className={"status " + cls} style={{ marginTop: 14, minHeight: 18 }}>{msg}</div>
        <div style={{ marginTop: 24, paddingTop: 16, borderTop: "1px solid var(--border)", color: "var(--muted)", fontSize: 12.5, lineHeight: 1.6 }}>
          白名单访问，无需注册。<br />
          只是来学习的？→ <a href="/">公开学习站</a>
        </div>
      </motion.div>
    </div>
  );
}
