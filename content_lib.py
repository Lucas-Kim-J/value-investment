#!/usr/bin/env python3
"""Shared content parsing — single source of truth for glossary terms & canon.

Used by both build.py (generates dist/assets/terms.json for the frontend term
wiki / ⌘K / hover) and seed.py (upserts into PostgreSQL on the server). Keeping
the parse here means glossary.md stays the git-versioned source of truth.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).parent
GLOSSARY_MD = ROOT / "routine" / "glossary.md"
CANON_JSON = ROOT / "content" / "canon.json"
ACHIEVEMENTS_JSON = ROOT / "content" / "achievements.json"

# keep a-z, 0-9 and CJK so Chinese-only terms get meaningful, stable slugs
_SLUG_RE = re.compile(r"[^a-z0-9一-鿿]+")


def slugify(s: str) -> str:
    s = (s or "").strip().lower()
    s = _SLUG_RE.sub("-", s).strip("-")
    return s or "term"


def parse_glossary(md_path: Path = GLOSSARY_MD) -> list[dict]:
    """Parse routine/glossary.md into term records.

    Format: `## Category` headers, then `**术语 (English)**` followed by a
    one-line definition that may end with `→ [详细](url)`.
    """
    if not Path(md_path).exists():
        return []
    lines = Path(md_path).read_text(encoding="utf-8").split("\n")
    terms: list[dict] = []
    category = ""
    seen: set[str] = set()
    i = 0
    while i < len(lines):
        line = lines[i]
        h = re.match(r"^##\s+(.*)", line)
        if h:
            category = h.group(1).strip()
            i += 1
            continue
        m = re.match(r"^\*\*(.+?)\*\*\s*$", line)
        if m:
            head = m.group(1).strip()
            pm = re.search(r"(.*?)\s*\(([^)]+)\)\s*$", head)
            if pm:
                term, en = pm.group(1).strip(), pm.group(2).strip()
            else:
                term, en = head, ""
            # definition = following lines until a blank / next term / header / rule
            buf = []
            j = i + 1
            while j < len(lines):
                s = lines[j]
                if s.strip() == "" or s.startswith("**") or s.startswith("##") or s.startswith("---") or s.startswith(">"):
                    break
                buf.append(s.strip())
                j += 1
            raw = " ".join(buf).strip()
            url_m = re.search(r"\[详细\]\(([^)]+)\)", raw)
            detail_url = url_m.group(1) if url_m else ""
            definition = re.sub(r"→?\s*\[详细\]\([^)]+\)", "", raw).strip()
            slug = slugify(en) if en else slugify(term)
            base, k = slug, 2
            while slug in seen:
                slug = f"{base}-{k}"
                k += 1
            seen.add(slug)
            terms.append({
                "slug": slug, "term": term, "en": en, "category": category,
                "definition": definition, "detail_url": detail_url,
            })
            i = j
            continue
        i += 1
    return terms


def load_canon() -> list[dict]:
    if CANON_JSON.exists():
        try:
            return json.loads(CANON_JSON.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"[warn] canon.json parse failed: {e}")
    return []


def load_achievements() -> list[dict]:
    if ACHIEVEMENTS_JSON.exists():
        try:
            return json.loads(ACHIEVEMENTS_JSON.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"[warn] achievements.json parse failed: {e}")
    return []


if __name__ == "__main__":
    t = parse_glossary()
    print(f"parsed {len(t)} terms")
    for x in t[:5]:
        print(f"  {x['slug']:28} {x['term']} ({x['en']}) [{x['category']}]")
