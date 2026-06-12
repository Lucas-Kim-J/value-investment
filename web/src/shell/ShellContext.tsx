import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { apiGet } from "../lib/api";
import type { AchievementsResp } from "../lib/types";
import { confetti } from "./confetti";
import { TermModal } from "./TermModal";
import { Cmdk } from "./Cmdk";

interface ToastItem { id: number; msg: string; ico?: string }
interface ShellApi {
  toast: (msg: string, ico?: string) => void;
  celebrate: (keys?: string[]) => void;
  openTerm: (slug: string) => void;
  openCmdk: () => void;
}

const ShellCtx = createContext<ShellApi | null>(null);
export function useShell(): ShellApi {
  const c = useContext(ShellCtx);
  if (!c) throw new Error("useShell must be used within ShellProvider");
  return c;
}

export function ShellProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const [termSlug, setTermSlug] = useState<string | null>(null);
  const [cmdkOpen, setCmdkOpen] = useState(false);
  const achTitles = useRef<Record<string, string>>({});
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

  // load achievement titles once (for celebrate labels)
  useEffect(() => {
    apiGet<AchievementsResp>("/api/achievements").then((r) => {
      if (r.data?.items) for (const a of r.data.items) achTitles.current[a.key] = a.title;
    });
  }, []);

  // global ⌘K / ⌘J hotkeys
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && (e.key === "k" || e.key === "K")) {
        e.preventDefault();
        setCmdkOpen(true);
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  const api: ShellApi = { toast, celebrate, openTerm, openCmdk };

  return (
    <ShellCtx.Provider value={api}>
      {children}
      <AnimatePresence>
        {cmdkOpen && <Cmdk key="cmdk" onClose={closeCmdk} onPick={openTerm} />}
        {termSlug && <TermModal key="term" slug={termSlug} onClose={closeTerm} onPick={openTerm} onCelebrate={celebrate} />}
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
