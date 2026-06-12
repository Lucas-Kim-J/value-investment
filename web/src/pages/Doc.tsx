import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getManifest, type DocMeta } from "../lib/docs";
import { DocHtml } from "./doc/DocHtml";
import { DocMarkdown } from "./doc/DocMarkdown";

export default function Doc() {
  const params = useParams();
  const path = (params["*"] || "").replace(/\/+$/, "");
  // undefined = loading, null = not found
  const [meta, setMeta] = useState<DocMeta | null | undefined>(undefined);
  const [content, setContent] = useState("");
  const [err, setErr] = useState("");

  useEffect(() => {
    let alive = true;
    setMeta(undefined);
    setContent("");
    setErr("");
    (async () => {
      try {
        const man = await getManifest();
        if (!alive) return;
        const m = man[path];
        if (!m) { setMeta(null); return; }
        setMeta(m);
        const r = await fetch("/content/" + path + (m.type === "md" ? ".md" : ".html"));
        if (!alive) return;
        if (!r.ok) { setErr("加载失败 " + r.status); return; }
        setContent(await r.text());
      } catch (e) {
        if (alive) { setMeta(null); setErr("加载失败：" + (e as Error).message); }
      }
    })();
    return () => { alive = false; };
  }, [path]);

  useEffect(() => {
    if (!meta?.title) return;
    const prev = document.title;
    document.title = meta.title + " · 价值投资学习 OS";
    return () => { document.title = prev; }; // restore when leaving the doc
  }, [meta]);

  // scroll to #hash for markdown docs (html docs handle it inside their shadow root)
  useEffect(() => {
    if (content && meta?.type === "md" && window.location.hash) {
      const el = document.getElementById(decodeURIComponent(window.location.hash.slice(1)));
      if (el) el.scrollIntoView({ behavior: "smooth" });
    }
  }, [content, meta]);

  return (
    <>
      <nav className="doc-nav">
        <Link to="/">🏠 首页</Link>
        <Link to="/doc/index">📖 方法论</Link>
        <Link to="/doc/routine/glossary">📚 术语</Link>
        {meta && path && <span className="doc-crumb">{path}</span>}
      </nav>

      {meta === undefined && !err && <p style={{ color: "var(--muted)" }}>加载中…</p>}

      {meta === null && !err && (
        <div className="app-head">
          <div className="eyebrow">Doc</div>
          <h1>文档不存在</h1>
          <p>没找到「{path}」。<Link to="/">返回首页</Link></p>
        </div>
      )}

      {err && <p className="status err" style={{ marginTop: 16 }}>{err}</p>}

      {meta && !err && content && (
        meta.type === "html"
          ? <DocHtml html={content} docPath={path} />
          : <DocMarkdown markdown={content} docPath={path} />
      )}
    </>
  );
}
