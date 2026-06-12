#!/usr/bin/env python3
"""Seed content (glossary terms, canon items, achievements) into PostgreSQL.

Content's source of truth is git (routine/glossary.md + content/*.json). This
script syncs it into the DB as a queryable copy — idempotent (ON CONFLICT
upsert), and NEVER deletes rows (so user learning_events pointing at a slug are
never orphaned). Run after deploy / on schema change:

    VI_DATABASE_URL=... python seed.py
    # local docker:  docker compose exec api python seed.py
"""
from __future__ import annotations

import json
import os
import sys

import psycopg2

import content_lib

DB_URL = os.environ.get("VI_DATABASE_URL", "")


def main() -> int:
    if not DB_URL:
        print("VI_DATABASE_URL not set", file=sys.stderr)
        return 1
    terms = content_lib.parse_glossary()
    canon = content_lib.load_canon()
    achs = content_lib.load_achievements()
    skills = content_lib.load_skills()

    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    for t in terms:
        cur.execute(
            """INSERT INTO glossary_terms(slug,term,term_en,category,definition,detail_url,related)
               VALUES (%s,%s,%s,%s,%s,%s,%s)
               ON CONFLICT (slug) DO UPDATE SET term=EXCLUDED.term, term_en=EXCLUDED.term_en,
                 category=EXCLUDED.category, definition=EXCLUDED.definition,
                 detail_url=EXCLUDED.detail_url, related=EXCLUDED.related""",
            (t["slug"], t["term"], t.get("en", ""), t.get("category", ""),
             t.get("definition", ""), t.get("detail_url", ""), t.get("related", [])),
        )

    for i, c in enumerate(canon):
        cur.execute(
            """INSERT INTO canon_items(slug,source,kind,title,period,official_url,coverage,tier,
                 est_minutes,why,guide,questions,related_terms,sort_order)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
               ON CONFLICT (slug) DO UPDATE SET source=EXCLUDED.source, kind=EXCLUDED.kind,
                 title=EXCLUDED.title, period=EXCLUDED.period, official_url=EXCLUDED.official_url,
                 coverage=EXCLUDED.coverage, tier=EXCLUDED.tier, est_minutes=EXCLUDED.est_minutes,
                 why=EXCLUDED.why, guide=EXCLUDED.guide, questions=EXCLUDED.questions,
                 related_terms=EXCLUDED.related_terms, sort_order=EXCLUDED.sort_order""",
            (c["slug"], c.get("source", ""), c.get("kind", ""), c.get("title", ""),
             c.get("period", ""), c.get("official_url", ""), c.get("coverage", "guide"),
             c.get("tier", ""), c.get("est_minutes", 0), c.get("why", ""), c.get("guide", ""),
             json.dumps(c.get("questions", []), ensure_ascii=False), c.get("related_terms", []), i),
        )

    for i, a in enumerate(achs):
        cur.execute(
            """INSERT INTO achievements(key,title,description,tier,icon,rule,sort_order)
               VALUES (%s,%s,%s,%s,%s,%s,%s)
               ON CONFLICT (key) DO UPDATE SET title=EXCLUDED.title, description=EXCLUDED.description,
                 tier=EXCLUDED.tier, icon=EXCLUDED.icon, rule=EXCLUDED.rule, sort_order=EXCLUDED.sort_order""",
            (a["key"], a.get("title", ""), a.get("desc", ""), a.get("tier", 1), a.get("icon", ""),
             json.dumps(a.get("rule", {}), ensure_ascii=False), i),
        )

    for s in skills:
        cur.execute(
            """INSERT INTO official_skills(name,version,description,skill_md,updated_at)
               VALUES (%s,%s,%s,%s,now())
               ON CONFLICT (name) DO UPDATE SET version=EXCLUDED.version,
                 description=EXCLUDED.description, skill_md=EXCLUDED.skill_md, updated_at=now()""",
            (s["name"], s.get("version", ""), s.get("description", ""), s["skill_md"]),
        )

    conn.commit()
    conn.close()
    print(f"✅ seeded: {len(terms)} terms · {len(canon)} canon · {len(achs)} achievements · {len(skills)} skills")
    return 0


if __name__ == "__main__":
    sys.exit(main())
