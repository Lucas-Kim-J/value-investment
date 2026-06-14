export interface DocMeta {
  type: "md" | "html";
  title: string;
}
export type DocManifest = Record<string, DocMeta>;

let _manifest: Promise<DocManifest> | null = null;
export function getManifest(): Promise<DocManifest> {
  if (!_manifest) {
    _manifest = fetch("/content/manifest.json")
      .then((r) => {
        if (!r.ok) throw new Error("manifest " + r.status);
        return r.json();
      })
      .catch((e) => {
        _manifest = null; // don't cache a transient failure — let the next call retry
        throw e;
      });
  }
  return _manifest;
}

// doc paths whose basename maps to a migrated React route rather than a /doc/* page
const APP_ROUTES: Record<string, string> = {
  dashboard: "/",
  login: "/login",
  wiki: "/wiki",
  portfolio: "/portfolio",
  analyze: "/analyze",
  canon: "/canon",
  achievements: "/achievements",
  learn: "/learn",
};

/** Resolve a doc-internal href (relative .md/.html / #anchor / external) to a SPA target.
 *  currentPath = the current doc's manifest key (no extension), e.g. "learning/failure-cases". */
export function resolveHref(
  href: string,
  currentPath: string,
): { to?: string; href?: string; hash?: string } {
  if (!href) return { href: "" };
  if (/^(https?:|mailto:|tel:)/i.test(href)) return { href };
  if (href.startsWith("#")) return { hash: href };
  const [rawPath, rawHash] = href.split("#");
  const hash = rawHash ? "#" + rawHash : "";
  if (!rawPath) return { hash };
  const dir = currentPath.includes("/") ? currentPath.slice(0, currentPath.lastIndexOf("/")) : "";
  const joined = rawPath.startsWith("/") ? rawPath.slice(1) : dir ? dir + "/" + rawPath : rawPath;
  const parts: string[] = [];
  for (const seg of joined.split("/")) {
    if (!seg || seg === ".") continue;
    if (seg === "..") parts.pop();
    else parts.push(seg);
  }
  const norm = parts.join("/").replace(/\.(md|html)$/i, "");
  if (APP_ROUTES[norm]) return { to: APP_ROUTES[norm], hash };
  return { to: "/doc/" + norm, hash };
}
