import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Link } from "react-router-dom";
import { apiGet, apiPost, me as fetchMe } from "../lib/api";
import { useMe } from "../lib/hooks";
import type { AsyncJob, ChatTurn } from "../lib/types";
import { Markdown } from "./Markdown";

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
const CHIPS = ["用我的水平解释一下", "这和我的持仓有什么关系", "出一道应用题考我"];

interface Msg {
  id: number;
  role: "user" | "bot";
  content: string;
  ctxLabel?: string;
  status?: "thinking" | "done" | "error";
  md?: boolean;
  kind?: "login";
}
export interface ChatPending { ctx?: string; ctxLabel?: string; prefill?: string }

export function Chat({
  open, setOpen, pending, clearPending, getPageContext,
}: {
  open: boolean;
  setOpen: (b: boolean) => void;
  pending: ChatPending | null;
  clearPending: () => void;
  getPageContext: () => string;
}) {
  const me = useMe();
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [ctx, setCtx] = useState<{ text: string; label: string } | null>(null);
  const [loaded, setLoaded] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const idRef = useRef(1);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; };
  }, []);

  const push = (m: Omit<Msg, "id">): number => {
    const id = idRef.current++;
    setMsgs((x) => [...x, { ...m, id }]);
    return id;
  };
  const patch = (id: number, p: Partial<Msg>) => setMsgs((x) => x.map((m) => (m.id === id ? { ...m, ...p } : m)));

  // load history once, on first open while logged in
  useEffect(() => {
    if (!open || !me || loaded) return;
    setLoaded(true);
    apiGet<{ items: ChatTurn[] }>("/api/chat").then((r) => {
      if (!mounted.current) return;
      const initial: Msg[] = [];
      for (const t of r.data?.items ?? []) {
        if (t.question) initial.push({ id: idRef.current++, role: "user", content: t.question });
        if (t.reply) initial.push({ id: idRef.current++, role: "bot", content: t.reply, status: "done", md: true });
      }
      setMsgs(initial);
    });
  }, [open, me, loaded]);

  // auto-scroll to newest
  useEffect(() => { if (open) scrollRef.current?.scrollTo({ top: 1e9 }); }, [msgs, open]);

  // focus the input on every open (matches vanilla toggleChat)
  useEffect(() => { if (open) setTimeout(() => inputRef.current?.focus(), 60); }, [open]);

  // textarea auto-grow
  useEffect(() => {
    const el = inputRef.current;
    if (el) { el.style.height = "auto"; el.style.height = Math.min(el.scrollHeight, 120) + "px"; }
  }, [input]);

  // consume an external request (selection→ask / page-context handoff)
  useEffect(() => {
    if (!pending) return;
    if (pending.ctx) setCtx({ text: pending.ctx, label: pending.ctxLabel || "「" + pending.ctx.slice(0, 50) + "」" });
    if (pending.prefill) setInput((prev) => (prev.trim() ? prev : pending.prefill!));
    clearPending();
    setTimeout(() => inputRef.current?.focus(), 50);
  }, [pending, clearPending]);

  async function sendChat(text?: string) {
    setOpen(true);
    let u = me;
    if (u === undefined) u = await fetchMe(); // resolve login on demand (vanilla awaits VI.me())
    if (!u) { push({ role: "bot", content: "", kind: "login", status: "done" }); return; }
    const q = (text ?? input).trim();
    if (!q) return;
    const c = ctx;
    setInput("");
    setCtx(null);
    push({ role: "user", content: q, ctxLabel: c?.label });
    const bid = push({ role: "bot", content: "思考中…", status: "thinking" });
    const r = await apiPost<{ id: number; error?: string }>("/api/chat", { question: q, context: c?.text || "" });
    if (r.status === 401) { patch(bid, { content: "请先登录", status: "error" }); return; }
    if (!r.ok || !r.data?.id) { patch(bid, { content: r.data?.error || "出错了", status: "error" }); return; }
    const id = r.data.id;
    const t0 = Date.now();
    while (mounted.current && Date.now() - t0 < 240000) {
      await sleep(2500);
      if (!mounted.current) return;
      let d: AsyncJob | null = null;
      try { d = (await apiGet<AsyncJob>("/api/chat/" + id)).data; } catch { continue; }
      if (!d) continue;
      if (d.status === "done") { patch(bid, { content: d.reply || "", status: "done", md: true }); return; }
      if (d.status === "error") { patch(bid, { content: d.error || "出错", status: "error" }); return; }
      patch(bid, { content: "思考中… " + Math.round((Date.now() - t0) / 1000) + "s", status: "thinking" });
    }
    patch(bid, { content: "超时，请重试", status: "error" });
  }

  function askThisPage() {
    const c = getPageContext();
    const name = ((document.querySelector(".app-head h1, h1")?.textContent) || document.title || "本页").trim().slice(0, 16);
    setCtx({ text: c, label: "本页：" + name });
    setInput((prev) => (prev.trim() ? prev : "结合这一页和我的水平，我该先读 / 先做哪个？给个顺序和理由"));
    inputRef.current?.focus();
  }

  const renderMsg = (m: Msg) => {
    if (m.role === "user") {
      return (
        <div key={m.id} className="vi-msg vi-msg-user">
          {m.ctxLabel && <span className="vi-ctx-tag">关于{m.ctxLabel}</span>}
          {m.ctxLabel ? " " : ""}{m.content}
        </div>
      );
    }
    return (
      <div key={m.id} className="vi-msg vi-msg-bot">
        {m.kind === "login" ? (
          <>请先 <Link to="/login">登录</Link> 再和我聊。</>
        ) : m.status === "done" && m.md ? (
          <Markdown className="vi-msg-md">{m.content}</Markdown>
        ) : (
          <span className={m.status === "thinking" || m.status === "error" ? "vi-think" : ""}>{m.content}</span>
        )}
      </div>
    );
  };

  return (
    <>
      <AnimatePresence>
        {!open && (
          <motion.button
            className="vi-chat-launcher" title="问 hermes (⌘J)" onClick={() => setOpen(true)}
            initial={{ scale: 0, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} exit={{ scale: 0, opacity: 0 }}
            transition={{ duration: 0.2, ease: [0.34, 1.56, 0.64, 1] }}
          >💬</motion.button>
        )}
      </AnimatePresence>

      <motion.div
        className="vi-chat-panel"
        style={{ pointerEvents: open ? "auto" : "none" }}
        initial={false}
        animate={open ? { opacity: 1, y: 0, scale: 1 } : { opacity: 0, y: 24, scale: 0.96 }}
        transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
      >
        <div className="vi-chat-head">
          <span>💬 hermes · 学习伙伴</span>
          <button className="x" onClick={() => setOpen(false)}>✕</button>
        </div>
        <div className="vi-chat-msgs" ref={scrollRef}>
          {msgs.length === 0 && (
            <div className="vi-msg vi-msg-bot">
              {me ? (
                "👋 我是 hermes。问我任何价值投资/方法论的问题；或在任意文章里划词 →「问 hermes」。我会按你的学习阶段回答。"
              ) : (
                <>👋 我是 hermes，你的学习伙伴。<Link to="/login">登录</Link>后就能问我问题——看文章时划词也能直接问我。</>
              )}
            </div>
          )}
          {msgs.map(renderMsg)}
        </div>
        {ctx && (
          <div className="vi-chat-ctx">
            <span>📎 {ctx.label}</span>
            <button onClick={() => setCtx(null)}>✕</button>
          </div>
        )}
        <div className="vi-chat-chips">
          <button className="vi-chip vi-chip-page" onClick={askThisPage}>📄 看这一页</button>
          {CHIPS.map((c) => <button key={c} className="vi-chip" onClick={() => sendChat(c)}>{c}</button>)}
        </div>
        <div className="vi-chat-input">
          <textarea
            ref={inputRef} rows={1} value={input} placeholder="问 hermes 任何问题… (Enter 发送)"
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendChat(); } }}
          />
          <button onClick={() => sendChat()}>↑</button>
        </div>
      </motion.div>
    </>
  );
}
