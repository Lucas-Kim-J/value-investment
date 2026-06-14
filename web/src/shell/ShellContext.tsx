import { createContext, lazy, Suspense, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { apiGet } from "../lib/api";
import type { AchievementsResp } from "../lib/types";
import { confetti } from "./confetti";
import { TermModal } from "./TermModal";
import { Cmdk } from "./Cmdk";
import type { ChatPending } from "./Chat";
import { SelectionToolbar } from "./SelectionToolbar";

// Chat + ExplainModal pull in react-markdown; lazy so it leaves the initial bundle.
const Chat = lazy(() => import("./Chat").then((m) => ({ default: m.Chat })));
const ExplainModal = lazy(() => import("./ExplainModal").then((m) => ({ default: m.ExplainModal })));

interface ToastItem { id: number; msg: string; ico?: string }
interface ShellApi {
  toast: (msg: string, ico?: string) => void;
  celebrate: (keys?: string[]) => void;
  openTerm: (slug: string) => void;
  openCmdk: () => void;
  toggleChat: () => void;
  askAbout: (text: string) => void;
  explain: (text: string, context?: string) => void;
  /** A page may register a digest of itself for the "看这一页" chat context. */
  setPageContext: (fn: (() => string) | null) => void;
}

const ShellCtx = createContext<ShellApi | null>(null);
export function useShell(): ShellApi {
  const c = useContext(ShellCtx);
  if (!c) throw new Error("useShell must be used within ShellProvider");
  return c;
}

/** Pages call this to expose a concise digest used by the chat "看这一页" chip. */
export function usePageContext(fn: () => string) {
  const { setPageContext } = useShell();
  const ref = useRef(fn);
  ref.current = fn;
  useEffect(() => {
    setPageContext(() => ref.current());
    return () => setPageContext(null);
  }, [setPageContext]);
}

export function ShellProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const [termSlug, setTermSlug] = useState<string | null>(null);
  const [cmdkOpen, setCmdkOpen] = useState(false);
  const [chatOpen, setChatOpen] = useState(false);
  const [chatPending, setChatPending] = useState<ChatPending | null>(null);
  const [explainReq, setExplainReq] = useState<{ text: string; context: string } | null>(null);
  const achTitles = useRef<Record<string, string>>({});
  const pageCtxRef = useRef<(() => string) | null>(null);
  const nextId = useRef(1);

  const toast = useCallback((msg: string, ico?: string) => {
    const id = nextId.current++;
    setToasts((t) => [...t, { id, msg, ico }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 3200);
  }, []);

  const celebrate = useCallback(
    (keys?: string[]) => {
      if (!keys || !keys.length) return;
      confetti();
      keys.forEach((k, i) => setTimeout(() => toast("解锁成就：" + (achTitles.current[k] || k), "🏅"), i * 900));
    },
    [toast],
  );

  const openTerm = useCallback((slug: string) => {
    setCmdkOpen(false);
    setTermSlug(slug);
  }, []);
  const openCmdk = useCallback(() => setCmdkOpen(true), []);
  const closeTerm = useCallback(() => setTermSlug(null), []);
  const closeCmdk = useCallback(() => setCmdkOpen(false), []);

  const toggleChat = useCallback(() => setChatOpen((o) => !o), []);
  const askAbout = useCallback((text: string) => {
    setChatPending({ ctx: text }); // Chat derives a 「…」-bracketed 50-char label
    setChatOpen(true);
  }, []);
  const explain = useCallback((text: string, context?: string) => setExplainReq({ text, context: context || "" }), []);
  const setPageContext = useCallback((fn: (() => string) | null) => { pageCtxRef.current = fn; }, []);
  const clearPending = useCallback(() => setChatPending(null), []);

  const getPageContext = useCallback(() => {
    try {
      if (pageCtxRef.current) {
        const s = pageCtxRef.current();
        if (s) return String(s).slice(0, 2800);
      }
    } catch { /* fall through to visible text */ }
    const title = (document.querySelector(".app-head h1, h1") as HTMLElement | null)?.textContent || document.title || "";
    const main = document.querySelector(".app-wrap, main, body") as HTMLElement | null;
    const txt = main ? (main.innerText || "").replace(/\n{2,}/g, "\n").trim() : "";
    return ("【页面】" + title + "\n" + txt).slice(0, 2500);
  }, []);

  // load achievement titles once (for celebrate labels)
  useEffect(() => {
    apiGet<AchievementsResp>("/api/achievements").then((r) => {
      if (r.data?.items) for (const a of r.data.items) achTitles.current[a.key] = a.title;
    });
  }, []);

  // global ⌘K (palette) / ⌘J (chat) hotkeys
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && (e.key === "k" || e.key === "K")) { e.preventDefault(); setCmdkOpen(true); }
      if ((e.metaKey || e.ctrlKey) && (e.key === "j" || e.key === "J")) { e.preventDefault(); setChatOpen((o) => !o); }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  const api: ShellApi = { toast, celebrate, openTerm, openCmdk, toggleChat, askAbout, explain, setPageContext };

  return (
    <ShellCtx.Provider value={api}>
      {children}

      <Suspense fallback={null}>
        <Chat open={chatOpen} setOpen={setChatOpen} pending={chatPending} clearPending={clearPending} getPageContext={getPageContext} />
      </Suspense>
      <SelectionToolbar onExplain={explain} onAsk={askAbout} />

      <AnimatePresence>
        {cmdkOpen && <Cmdk key="cmdk" onClose={closeCmdk} onPick={openTerm} />}
        {termSlug && <TermModal key="term" slug={termSlug} onClose={closeTerm} onPick={openTerm} onCelebrate={celebrate} />}
        {explainReq && (
          <Suspense key="explain" fallback={null}>
            <ExplainModal
              text={explainReq.text}
              context={explainReq.context}
              onClose={() => setExplainReq(null)}
              toast={toast}
              celebrate={celebrate}
              openTerm={openTerm}
              askAbout={askAbout}
            />
          </Suspense>
        )}
      </AnimatePresence>

      <div style={{ position: "fixed", bottom: 24, left: "50%", transform: "translateX(-50%)", zIndex: 200, display: "flex", flexDirection: "column", gap: 8, alignItems: "center" }}>
        <AnimatePresence>
          {toasts.map((t) => (
            <motion.div
              key={t.id}
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 8 }}
              transition={{ duration: 0.24, ease: [0.34, 1.56, 0.64, 1] }}
              style={{ background: "var(--fg)", color: "var(--bg)", padding: "12px 20px", borderRadius: 10, fontSize: 14, boxShadow: "0 8px 30px rgba(0,0,0,.3)" }}
            >
              {t.ico && <span style={{ marginRight: 8 }}>{t.ico}</span>}
              {t.msg}
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </ShellCtx.Provider>
  );
}
