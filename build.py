#!/usr/bin/env python3
"""Static site generator for the value-investing learning system.

Converts every Markdown file into a styled, mobile-friendly HTML page that
matches the hand-made v1.1 pages, copies the existing HTML pages, and rewrites
internal `.md` links to `.html`. Output goes to `dist/`, mirroring the repo
structure, ready to be rsynced to the server web root.

Usage:
    python build.py            # build into ./dist
    python build.py --serve    # build, then serve dist/ at http://localhost:8000

Design goals:
  - One command. Re-run any time markdown changes; the site rebuilds.
  - Source of truth stays in Markdown — easy to write, git-friendly.
  - dist/ is a build artifact (gitignored); CI rebuilds it on deploy.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

try:
    import markdown
except ImportError:
    sys.exit("缺少依赖：pip install -r requirements-build.txt  (markdown)")

ROOT = Path(__file__).parent.resolve()
DIST = ROOT / "dist"

# Directories never included in the site
SKIP_DIRS = {".git", "dist", "node_modules", ".github", "journals", "__pycache__", ".venv", "venv", "assets", "skills", "web"}
# Files we never publish as pages
SKIP_FILES = {".gitignore", "requirements-build.txt"}

# Rewrite internal links: foo/bar.md(#anchor) -> foo/bar.html(#anchor)
# but leave absolute URLs (http/https/mailto) alone.
MD_LINK_RE = re.compile(r'(href=")(?!https?://|mailto:|#)([^"]*?)\.md(#[^"]*)?(")')


def rewrite_md_links(html: str) -> str:
    return MD_LINK_RE.sub(lambda m: f'{m.group(1)}{m.group(2)}.html{m.group(3) or ""}{m.group(4)}', html)


# No-flash guard: mark <html> for motion synchronously in <head>, with a 3s
# fallback that reveals everything in case motion.js never loads (content is
# never trapped hidden).
HEAD_MOTION = (
    "<script>document.documentElement.classList.add('vi-motion');"
    "setTimeout(function(){if(!document.documentElement.getAttribute('data-vi-ready'))"
    "[].forEach.call(document.querySelectorAll('[data-reveal]'),function(e){e.classList.add('is-in')})},3000)</script>"
)


def inject_motion(html: str, root: str) -> str:
    """Inject the motion layer (CSS + head guard + JS) into a finished page. Idempotent."""
    if "assets/motion.css" not in html:
        head = f'{HEAD_MOTION}\n<link rel="stylesheet" href="{root}assets/motion.css">'
        html = html.replace("</head>", head + "\n</head>", 1)
    if "assets/motion.js" not in html:
        html = html.replace("</body>", f'<script src="{root}assets/motion.js"></script>\n</body>', 1)
    return html


def wrap_tables(html: str) -> str:
    """Wrap <table> in a horizontally-scrollable div for mobile."""
    return html.replace("<table>", '<div class="table-wrap"><table>').replace("</table>", "</table></div>")


def first_h1(md_text: str) -> str | None:
    for line in md_text.splitlines():
        s = line.strip()
        if s.startswith("# "):
            return s[2:].strip()
    return None


def rel_root(rel_path: Path) -> str:
    """Relative prefix from a page back to the site root (e.g. '../')."""
    depth = len(rel_path.parts) - 1
    return "../" * depth if depth else ""


def breadcrumb(rel_path: Path) -> str:
    return " / ".join(rel_path.parts)


PAGE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title} · 价值投资系统</title>
<link rel="stylesheet" href="{root}assets/style.css">
<link rel="stylesheet" href="{root}assets/app.css">
</head>
<body class="md-page">
<div class="md-container">
  <nav class="topnav">
    <a href="{root}dashboard.html">🏠 Dashboard</a>
    <a href="{root}index.html">📖 方法论</a>
    <a href="{root}routine/glossary.html">📚 术语</a>
    <span class="crumb">{crumb}</span>
  </nav>
{toc}
  <main class="md-body">
{body}
  </main>
  <footer class="md-footer">
    <p>价值投资学习系统 · <a href="{root}dashboard.html">返回 Dashboard</a></p>
    <p class="src">源文件：<code>{src}</code> · 由 build.py 生成</p>
  </footer>
</div>
<script src="{root}assets/app.js"></script>
</body>
</html>
"""


def convert_markdown(md_path: Path) -> str:
    rel = md_path.relative_to(ROOT)
    text = md_path.read_text(encoding="utf-8")

    md = markdown.Markdown(
        extensions=["extra", "sane_lists", "toc", "admonition"],
        extension_configs={"toc": {"permalink": False}},
    )
    body = md.convert(text)
    body = wrap_tables(rewrite_md_links(body))

    # Build a collapsible TOC for longer docs
    heading_count = len(re.findall(r"<h[23][ >]", body))
    toc_html = ""
    if heading_count >= 4 and getattr(md, "toc", "").strip():
        toc_inner = rewrite_md_links(md.toc)
        toc_html = f'  <details class="toc-box"><summary>目录</summary>{toc_inner}</details>'

    title = first_h1(text) or rel.stem
    return PAGE.format(
        title=title,
        root=rel_root(rel),
        crumb=breadcrumb(rel),
        toc=toc_html,
        body=body,
        src=rel.as_posix(),
    )


def iter_files():
    for p in ROOT.rglob("*"):
        if not p.is_file():
            continue
        parts = set(p.relative_to(ROOT).parts[:-1])
        if parts & SKIP_DIRS:
            continue
        if p.name in SKIP_FILES:
            continue
        yield p


def build() -> None:
    # clean dist *contents* (not the dir itself) so docker bind-mounts stay valid
    DIST.mkdir(parents=True, exist_ok=True)
    for child in DIST.iterdir():
        shutil.rmtree(child) if child.is_dir() else child.unlink()

    # shared assets
    shutil.copytree(ROOT / "assets", DIST / "assets")

    # terms.json for the global ⌘K term search (frontend reads /assets/terms.json)
    import content_lib
    _terms = content_lib.parse_glossary()
    (DIST / "assets" / "terms.json").write_text(
        json.dumps(
            [{"slug": t["slug"], "term": t["term"], "en": t.get("en", ""),
              "definition": t.get("definition", ""), "detail_url": t.get("detail_url", ""),
              "category": t.get("category", "")} for t in _terms],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    md_count = html_count = 0
    for src in iter_files():
        rel = src.relative_to(ROOT)
        if src.suffix == ".md":
            out = DIST / rel.with_suffix(".html")
            out.parent.mkdir(parents=True, exist_ok=True)
            html = inject_motion(convert_markdown(src), rel_root(rel.with_suffix(".html")))
            out.write_text(html, encoding="utf-8")
            md_count += 1
        elif src.suffix == ".html":
            out = DIST / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            # Copy existing hand-made pages, but rewrite their .md links -> .html
            html = inject_motion(rewrite_md_links(src.read_text(encoding="utf-8")), rel_root(rel))
            out.write_text(html, encoding="utf-8")
            html_count += 1

    total = md_count + html_count
    print(f"✅ built {total} pages → {DIST.relative_to(ROOT)}/  ({md_count} from markdown, {html_count} html copied)")
    print(f"   入口：dist/dashboard.html")


def serve() -> None:
    import http.server
    import os
    import socketserver

    os.chdir(DIST)
    port = 8000
    with socketserver.TCPServer(("", port), http.server.SimpleHTTPRequestHandler) as httpd:
        print(f"🌐 serving dist/ at http://localhost:{port}/dashboard.html  (Ctrl+C to stop)")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nstopped")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Build the value-investing static site")
    ap.add_argument("--serve", action="store_true", help="Serve dist/ locally after building")
    args = ap.parse_args(argv)
    build()
    if args.serve:
        serve()


if __name__ == "__main__":
    main()
