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
SKIP_DIRS = {".git", "dist", "node_modules", ".github", "journals", "__pycache__", ".venv", "venv", "assets"}
# Files we never publish as pages
SKIP_FILES = {".gitignore", "requirements-build.txt"}

# Rewrite internal links: foo/bar.md(#anchor) -> foo/bar.html(#anchor)
# but leave absolute URLs (http/https/mailto) alone.
MD_LINK_RE = re.compile(r'(href=")(?!https?://|mailto:|#)([^"]*?)\.md(#[^"]*)?(")')


def rewrite_md_links(html: str) -> str:
    return MD_LINK_RE.sub(lambda m: f'{m.group(1)}{m.group(2)}.html{m.group(3) or ""}{m.group(4)}', html)


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
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir(parents=True)

    # shared assets
    shutil.copytree(ROOT / "assets", DIST / "assets")

    md_count = html_count = 0
    for src in iter_files():
        rel = src.relative_to(ROOT)
        if src.suffix == ".md":
            out = DIST / rel.with_suffix(".html")
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(convert_markdown(src), encoding="utf-8")
            md_count += 1
        elif src.suffix == ".html":
            out = DIST / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            # Copy existing hand-made pages, but rewrite their .md links -> .html
            out.write_text(rewrite_md_links(src.read_text(encoding="utf-8")), encoding="utf-8")
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
