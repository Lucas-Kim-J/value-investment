# value-investment — React SPA (`web/`)

The frontend, migrated from the vanilla `build.py`-generated static site to a
React single-page app. Same Flask + PostgreSQL backend, same `/api/*` contracts —
**only the frontend changed.** The live site is served from `web/dist/` (built by
Vite) behind nginx, with `/api/*` proxied to the gunicorn app.

> Migration done on branch `v4-react`. The old vanilla pages (`*.html` at the repo
> root) and `build.py` still exist; this app reaches parity and replaces them on
> deploy. Doc *content* (方法论, routines, …) is still authored as HTML/Markdown at
> the repo root and pulled in at build time — see [Doc system](#doc-system).

## Stack

React 18 · TypeScript · Vite · react-router-dom v6 · framer-motion ·
react-markdown + remark-gfm + rehype-slug.

## Layout

```
src/
  main.tsx            entry → RouterProvider(router)
  App.tsx             router; pages are React.lazy (one chunk each)
  app/
    Layout.tsx        <ShellProvider> + Nav + animated <Outlet> (Suspense)
    Nav.tsx           top nav + ⌘K button + user chip
  shell/              global, always-mounted UI (the "shell")
    ShellContext.tsx  ShellProvider + useShell() + usePageContext()
    Chat.tsx          hermes chat panel (⌘J) — lazy
    ExplainModal.tsx  划词「解释」card → 收入术语库 — lazy
    SelectionToolbar  select-to-ask floating toolbar
    Cmdk.tsx          ⌘K term palette
    TermModal.tsx     term card (费曼 mastery gate)
    Markdown.tsx      shared react-markdown wrapper
    confetti.ts       achievement confetti
  pages/              one file per route (+ subfolders for big pages)
    Dashboard, Wiki, Achievements, Learn, Canon(+CanonModal),
    Portfolio(+portfolio/*), Analyze, Doc(+doc/*), Login, Stub
  lib/
    api.ts            api()/apiGet/apiPost/... → {ok,status,data}; me()
    hooks.ts          useMe() → string|null|undefined (undefined = loading)
    types.ts          all API response types
    docs.ts           doc manifest fetch + resolveHref() link rewriter
  styles/global.css   design tokens + every component class (ported from vanilla)
```

The **shell** (nav, ⌘K, toasts, chat, select-to-ask, modals) lives in
`ShellProvider` and is available on every in-app route via `useShell()`.
Pages opt into the chat's "看这一页" context with `usePageContext(() => digest)`.

## Doc system (`/doc/*`)

Long-form content is a mix the SPA renders two ways (`pages/Doc.tsx`):

- **Bespoke HTML** — `index.html` (方法论, 665 lines w/ its own `<style>`),
  `learning/*.html`, `product-vision.html`. These are injected into a **shadow
  root** (`doc/DocHtml.tsx`) so their ~50 page-specific classes and
  generic-element rules can't leak onto the app. Pixel-perfect, zero CSS porting.
  In-page `#anchor` clicks and the initial `#hash` scroll within the shadow tree;
  internal links are intercepted → SPA navigation.
- **Markdown** — `routine/*.md`, `research/*.md`, etc. rendered with
  react-markdown (`doc/DocMarkdown.tsx`): slugged headings (rehype-slug), a
  collapsible 目录 for docs with ≥4 headings, mobile-wrapped tables.

Both rewrite internal `.md`/`.html` links to SPA routes via `lib/docs.ts`
`resolveHref()` (app pages → `/wiki` etc.; other docs → `/doc/<path>`).

### Content sync

`scripts/sync-content.mjs` (run by `npm run build`, and on demand via
`npm run sync-content`) walks the repo root — mirroring `build.py`'s publish set
— and copies docs into `public/content/`:
- `.md` → copied raw (rendered client-side)
- bespoke `.html` → `<style>`+`<body>` extracted (scripts/links stripped)
- writes `content/manifest.json`: `{ "<path>": { type: "md"|"html", title } }`

`public/content/` is **generated** (gitignored). App `.html` pages
(dashboard/wiki/…) are excluded — they're React routes now.

## Dev

```bash
npm install
npm run sync-content   # populate public/content/ once (also runs in build)
npm run dev            # vite @ :5173, proxies /api → http://localhost:8080
```
Log in via the dev access code against the running backend (docker stack at :8080).

## Build & deploy

```bash
npm run build          # sync-content + tsc + vite build → dist/
./deploy.sh            # build + rsync dist/ → openclaw:/var/www/value-investment/
./deploy.sh --dry-run  # preview the file changes, transfer nothing
```

One-time on the server: install the SPA vhost so client routes fall back to the
app shell and old `*.html` bookmarks redirect:
```bash
scp ../server/nginx-value-investment-spa.conf openclaw:/tmp/
ssh openclaw 'sudo cp /tmp/nginx-value-investment-spa.conf \
  /etc/nginx/sites-available/value-investment && sudo nginx -t && sudo systemctl reload nginx'
```
The vhost serves `/assets/` + `/content/` as files, proxies `/api/`, redirects
legacy `*.html` URLs (`/dashboard.html`→`/`, `/learning/x.html`→`/doc/learning/x`,
`/index.html`→`/doc/index`), and falls back everything else to `index.html`.

## Code-splitting

- Each route is `React.lazy` → its own chunk, fetched on navigation.
- `Chat`/`ExplainModal` are lazy too, so **react-markdown leaves the first-paint
  path** (loads when the chat mounts / a markdown route opens).
- `vite.config.ts` `manualChunks` splits `react`/`react-dom`/router and
  `framer-motion` into separate long-cache vendor chunks.

## Gotchas / notes

- **Shadow-DOM selection**: select-to-ask reads `ShadowRoot.getSelection()`
  (Chrome) so it works inside bespoke `/doc` HTML. `document.getElementById`
  won't find shadow content — `DocHtml` scrolls within its own shadow root.
- **`useMe()` is tri-state**: `undefined` = loading, `null` = logged out,
  `string` = user. Guard accordingly (the chat awaits `me()` on demand so a
  click during the in-flight `/api/me` isn't dropped).
- **Stable callbacks**: shell `closeTerm`/`closeCmdk`/`clearPending` are
  `useCallback`s — TermModal's fetch effect depends only on `[slug]` to avoid
  refetch loops (an earlier bug).
- **macOS `openrsync`** doesn't print `deleting …` lines in a plain
  `-avn --delete` dry-run; use `rsync -ain --delete | grep '^\*deleting'` to see
  what `--delete` would remove.
- **`public/content/` and `dist/` are generated** — never edit by hand, never commit.
