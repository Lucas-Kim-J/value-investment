import { useEffect, useState } from "react";

interface SelState { text: string; ctx: string; top: number; left: number }

/** Reads the active selection, preferring a doc shadow root's selection (Chrome's
 *  ShadowRoot.getSelection) so select-to-ask also works inside the bespoke /doc HTML. */
function activeSelection(): Selection | null {
  const light = window.getSelection();
  if (light && light.toString().trim()) return light;
  const host = document.querySelector(".doc-html-host");
  const sr = host?.shadowRoot as (ShadowRoot & { getSelection?: () => Selection | null }) | undefined;
  if (sr?.getSelection) {
    const s = sr.getSelection();
    if (s && s.toString().trim()) return s;
  }
  return light;
}

/** Floating "🔍 解释 / 💬 问 hermes" toolbar shown on a text selection. */
export function SelectionToolbar({
  onExplain, onAsk,
}: {
  onExplain: (text: string, ctx: string) => void;
  onAsk: (text: string) => void;
}) {
  const [sel, setSel] = useState<SelState | null>(null);

  useEffect(() => {
    const onUp = (e: MouseEvent) => {
      const t = e.target as HTMLElement;
      // skip the chat panel, ⌘K palette and interactive controls — content stays selectable
      if (t.closest?.(".vi-chat-panel, .vi-cmdk, input, textarea, .vi-sel-toolbar, button, a")) return;
      setTimeout(() => {
        const s = activeSelection();
        const text = (s ? s.toString() : "").trim();
        if (text.length < 2 || text.length > 120 || !s || !s.rangeCount) { setSel(null); return; }
        const range = s.getRangeAt(0);
        const node = range.startContainer;
        const blk = node.nodeType === 3 ? node.parentElement : (node as HTMLElement);
        const ctx = (blk?.textContent || "").trim().slice(0, 300);
        const rect = range.getBoundingClientRect();
        const tw = 150, th = 34;
        let top = rect.bottom + 8;
        let left = rect.left;
        if (top + th > window.innerHeight - 8) top = Math.max(8, rect.top - th - 8); // flip above
        left = Math.max(8, Math.min(left, window.innerWidth - tw - 8)); // clamp to viewport
        setSel({ text, ctx, top, left });
      }, 10);
    };
    const onDown = (e: MouseEvent) => {
      if (!(e.target as HTMLElement).closest?.(".vi-sel-toolbar")) setSel(null);
    };
    const onScroll = () => setSel(null);
    document.addEventListener("mouseup", onUp);
    document.addEventListener("mousedown", onDown);
    window.addEventListener("scroll", onScroll, true);
    return () => {
      document.removeEventListener("mouseup", onUp);
      document.removeEventListener("mousedown", onDown);
      window.removeEventListener("scroll", onScroll, true);
    };
  }, []);

  if (!sel) return null;
  return (
    <div className="vi-sel-toolbar" style={{ top: sel.top, left: sel.left }}>
      <button onMouseDown={(e) => e.preventDefault()} onClick={() => { onExplain(sel.text, sel.ctx); setSel(null); }}>🔍 解释</button>
      <button onMouseDown={(e) => e.preventDefault()} onClick={() => { onAsk(sel.text); setSel(null); }}>💬 问 hermes</button>
    </div>
  );
}
