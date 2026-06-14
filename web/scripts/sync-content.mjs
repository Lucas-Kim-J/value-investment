// Sync repo doc content into web/public/content/ for the SPA's /doc/* routes.
//   - markdown files  → copied raw (rendered client-side via react-markdown)
//   - bespoke .html    → <style>+<body> extracted (scripts/links stripped), rendered in a shadow root
// Writes manifest.json mapping each doc path (no extension) → { type, title }.
// Run before `vite build` (wired into npm "build") and once for local dev.
import { readdir, readFile, writeFile, mkdir, rm } from "node:fs/promises";
import { join, relative, dirname, extname } from "node:path";

const WEB = process.cwd(); // npm runs scripts from the package dir (web/)
const ROOT = join(WEB, ".."); // repo root
const OUT = join(WEB, "public", "content");

// dirs never published (mirrors build.py SKIP_DIRS) + web itself
const SKIP_DIRS = new Set([
  ".git", "dist", "node_modules", ".github", "journals", "__pycache__",
  ".venv", "venv", "assets", "skills", "web", ".claude", ".idea",
]);
// .html pages that became React routes — never serve them as docs
const APP_PAGES = new Set([
  "dashboard.html", "wiki.html", "portfolio.html", "analyze.html",
  "canon.html", "achievements.html", "learn.html", "login.html",
]);

async function walk(dir, acc = []) {
  for (const ent of await readdir(dir, { withFileTypes: true })) {
    if (ent.isDirectory()) {
      if (!SKIP_DIRS.has(ent.name)) await walk(join(dir, ent.name), acc);
    } else acc.push(join(dir, ent.name));
  }
  return acc;
}

const firstH1 = (text) => {
  for (const line of text.split("\n")) {
    const s = line.trim();
    if (s.startsWith("# ")) return s.slice(2).trim();
  }
  return null;
};
const htmlTitle = (html) => {
  const t = html.match(/<title>([^<]*)<\/title>/i);
  if (t) return t[1].split("·")[0].trim();
  const h = html.match(/<h1[^>]*>([\s\S]*?)<\/h1>/i);
  return h ? h[1].replace(/<[^>]+>/g, "").trim() : null;
};
const styleAndBody = (html) => {
  const styles = [...html.matchAll(/<style[\s\S]*?<\/style>/gi)].map((m) => m[0]).join("\n");
  const bodyM = html.match(/<body[^>]*>([\s\S]*?)<\/body>/i);
  let body = bodyM ? bodyM[1] : html;
  body = body.replace(/<script[\s\S]*?<\/script>/gi, ""); // strip scripts
  body = body.replace(/<style[\s\S]*?<\/style>/gi, ""); // strip in-body styles (already hoisted into `styles`)
  body = body.replace(/<link\b[^>]*>/gi, ""); // strip external stylesheet/link refs
  return styles + "\n" + body;
};

async function main() {
  await rm(OUT, { recursive: true, force: true });
  await mkdir(OUT, { recursive: true });
  const files = await walk(ROOT);
  // process .md before .html so markdown wins if both exist for the same path
  files.sort((a, b) => (extname(a) === ".md" ? 0 : 1) - (extname(b) === ".md" ? 0 : 1));

  const manifest = {};
  for (const abs of files) {
    const rel = relative(ROOT, abs).split("\\").join("/");
    const ext = extname(abs).toLowerCase();
    if (ext === ".md") {
      const key = rel.replace(/\.md$/i, "");
      if (manifest[key]) continue;
      const text = await readFile(abs, "utf8");
      const out = join(OUT, rel);
      await mkdir(dirname(out), { recursive: true });
      await writeFile(out, text);
      manifest[key] = { type: "md", title: firstH1(text) || key.split("/").pop() };
    } else if (ext === ".html") {
      const base = rel.split("/").pop();
      if (APP_PAGES.has(base)) continue;
      const key = rel.replace(/\.html$/i, "");
      if (manifest[key]) continue;
      const html = await readFile(abs, "utf8");
      const out = join(OUT, rel);
      await mkdir(dirname(out), { recursive: true });
      await writeFile(out, styleAndBody(html));
      manifest[key] = { type: "html", title: htmlTitle(html) || key.split("/").pop() };
    }
  }
  await writeFile(join(OUT, "manifest.json"), JSON.stringify(manifest));
  console.log(`synced ${Object.keys(manifest).length} docs → web/public/content/`);
}
main().catch((e) => { console.error(e); process.exit(1); });
