import { useEffect, useRef } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { resolveHref } from "../../lib/docs";

/** Renders a bespoke doc's self-contained <style>+<body> inside a shadow root so its
 *  ~50 page-specific classes and generic-element rules can't leak onto the app shell.
 *  Intercepts internal link clicks → SPA navigation; #anchors scroll within the shadow tree. */
export function DocHtml({ html, docPath }: { html: string; docPath: string }) {
  const hostRef = useRef<HTMLDivElement>(null);
  const nav = useNavigate();
  const loc = useLocation();

  // inject content + intercept internal link clicks
  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;
    const shadow = host.shadowRoot || host.attachShadow({ mode: "open" });
    shadow.innerHTML = html;

    const onClick = (e: Event) => {
      const a = (e.target as HTMLElement)?.closest?.("a") as HTMLAnchorElement | null;
      if (!a) return;
      const raw = a.getAttribute("href") || "";
      if (!raw) return;
      const res = resolveHref(raw, docPath);
      if (res.hash && !res.to && !res.href) {
        // in-page anchor: scroll within the shadow tree, no router/history change
        e.preventDefault();
        const el = shadow.getElementById(decodeURIComponent(res.hash.slice(1)));
        if (el) (el as HTMLElement).scrollIntoView({ behavior: "smooth", block: "start" });
        return;
      }
      if (res.to) {
        e.preventDefault();
        nav(res.to + (res.hash || ""));
      }
      // external (res.href present): allow default navigation
    };
    shadow.addEventListener("click", onClick);
    return () => shadow.removeEventListener("click", onClick);
  }, [html, docPath, nav]);

  // honor an incoming #hash (initial load, in-app nav, and browser back/forward)
  useEffect(() => {
    const shadow = hostRef.current?.shadowRoot;
    if (!shadow || !loc.hash) return;
    const el = shadow.getElementById(decodeURIComponent(loc.hash.slice(1)));
    if (el) requestAnimationFrame(() => (el as HTMLElement).scrollIntoView({ behavior: "smooth", block: "start" }));
  }, [loc.hash, html]);

  return <div ref={hostRef} className="doc-html-host" />;
}
