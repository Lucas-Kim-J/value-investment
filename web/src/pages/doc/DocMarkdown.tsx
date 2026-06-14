import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeSlug from "rehype-slug";
import { Link } from "react-router-dom";
import { resolveHref } from "../../lib/docs";

interface TocItem { id: string; text: string; sub: boolean }

/** Markdown docs rendered with the shared design system. Mirrors build.py: slugged
 *  heading ids, a collapsible 目录 for docs with ≥4 headings, mobile-scrollable tables,
 *  and internal .md/.html links rewritten to SPA routes. */
export function DocMarkdown({ markdown, docPath }: { markdown: string; docPath: string }) {
  const bodyRef = useRef<HTMLDivElement>(null);
  const [toc, setToc] = useState<TocItem[]>([]);

  // build the TOC from rendered (rehype-slug'd) headings after each doc change
  useEffect(() => {
    if (!bodyRef.current) return;
    const hs = [...bodyRef.current.querySelectorAll("h2, h3")] as HTMLElement[];
    setToc(hs.filter((h) => h.id).map((h) => ({ id: h.id, text: h.textContent || "", sub: h.tagName === "H3" })));
  }, [markdown]);

  const jump = (e: React.MouseEvent, id: string) => {
    e.preventDefault();
    bodyRef.current?.ownerDocument.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  return (
    <>
      {toc.length >= 4 && (
        <details className="toc-box">
          <summary>目录</summary>
          <ul>
            {toc.map((t) => (
              <li key={t.id} className={t.sub ? "sub" : ""}>
                <a href={"#" + t.id} onClick={(e) => jump(e, t.id)}>{t.text}</a>
              </li>
            ))}
          </ul>
        </details>
      )}
      <div className="md-render" ref={bodyRef}>
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          rehypePlugins={[rehypeSlug]}
          components={{
            a({ href, children, ...props }) {
              const res = resolveHref(href || "", docPath);
              if (res.to) return <Link to={res.to + (res.hash || "")}>{children}</Link>;
              if (res.hash && !res.href) return <a href={res.hash} {...props}>{children}</a>;
              return <a href={res.href} target="_blank" rel="noreferrer" {...props}>{children}</a>;
            },
            table({ children, ...props }) {
              return <div className="table-wrap"><table {...props}>{children}</table></div>;
            },
          }}
        >
          {markdown}
        </ReactMarkdown>
      </div>
    </>
  );
}
