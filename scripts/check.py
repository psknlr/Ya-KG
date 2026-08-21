#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Verify a built Ya-KG site.

  python3 scripts/check.py dist

Checks: source-data integrity, required outputs, every internal link/asset
reference resolving to a real file, JSON validity, and sitemap coverage.
Exits non-zero on the first category that fails, so CI can gate on it.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parent.parent
HREF = re.compile(r'(?:href|src)\s*=\s*"([^"]+)"', re.I)
SKIP = ("http://", "https://", "//", "mailto:", "tel:", "data:", "javascript:", "#")

fails: list[str] = []
PARTIAL = False   # set when checking a --skip-concepts preview build


def fail(cat: str, msg: str):
    fails.append(f"{cat}: {msg}")


def check_source_data():
    kg = json.loads((ROOT / "data" / "kg.json").read_text("utf-8"))
    vocab = json.loads((ROOT / "data" / "vocab.json").read_text("utf-8"))
    T, R, CH, N, E, F, P = kg["T"], kg["R"], kg["CH"], kg["N"], kg["E"], kg["F"], kg["P"]
    n = len(N)

    for k, v in kg["meta"].items():
        pass
    expect = {"n": len(N), "e": len(E), "f": len(F), "p": len(P)}
    for key, got in expect.items():
        if kg["meta"][key] != got:
            fail("data", f"meta.{key}={kg['meta'][key]} but array has {got} rows")

    for i, r in enumerate(N):
        if len(r) != 8:
            fail("data", f"N[{i}] has {len(r)} fields, expected 8")
            break
        if not 0 <= r[2] < len(T):
            fail("data", f"N[{i}] type index {r[2]} out of range")
        if not r[0]:
            fail("data", f"N[{i}] has an empty name")

    names = [r[0] for r in N]
    if len(set(names)) != len(names):
        dupes = {x for x in names if names.count(x) > 1}
        fail("data", f"entity names are not unique: {sorted(dupes)[:5]}")

    for k, e in enumerate(E):
        if len(e) != 5:
            fail("data", f"E[{k}] has {len(e)} fields, expected 5")
            break
        if not (0 <= e[0] < n and 0 <= e[1] < n):
            fail("data", f"E[{k}] references a node out of range: {e[0]} -> {e[1]}")
        if not 0 <= e[2] < len(R):
            fail("data", f"E[{k}] predicate index {e[2]} out of range")

    for k, f in enumerate(F):
        if not 0 <= f[0] < n:
            fail("data", f"F[{k}] entity index {f[0]} out of range")
    for k, p in enumerate(P):
        if not 0 <= p[0] < n:
            fail("data", f"P[{k}] entity index {p[0]} out of range")

    missing = sorted(set(T) - set(vocab["types"]))
    if missing:
        fail("vocab", f"types missing a label in vocab.json: {missing}")
    missing = sorted(set(R) - set(vocab["relations"]))
    if missing:
        fail("vocab", f"relations missing a label in vocab.json: {missing}")

    chapters = {c for r in N for c in r[5]}
    unknown = sorted(c for c in chapters if str(c) not in CH)
    if unknown:
        fail("data", f"entities reference chapters absent from CH: {unknown}")

    print(f"  data      {n:,} entities · {len(E):,} relations · {len(F):,} facts · {len(P):,} params")
    return kg


def check_outputs(out: Path, kg):
    required = [
        "index.html", "404.html", ".nojekyll", "robots.txt", "sitemap.xml",
        "sitemap-pages.xml", "sitemap-concepts.xml", "manifest.webmanifest", "sw.js",
        "explorer/index.html", "glossary/index.html", "parameters/index.html",
        "cards/index.html", "stats/index.html", "about/index.html",
        "chapters/index.html", "downloads/index.html",
        "assets/css/app.css", "assets/js/core.js", "assets/img/og.png", "assets/img/favicon.svg",
        "data/kg.json", "data/search.json", "data/glossary.json",
        "data/parameters.json", "data/stats.json",
        "downloads/kg-entities.csv", "downloads/kg-relations.csv", "downloads/kg.jsonl",
        "downloads/kg-neo4j.cypher", "downloads/kg.ttl", "downloads/kg-anki.csv",
    ]
    for ch in kg["CH"]:
        required.append(f"chapters/{ch}/index.html")
        required.append(f"data/cards/ch{ch}.json")
    for rel in required:
        if not (out / rel).is_file():
            fail("outputs", f"missing {rel}")

    n = len(kg["N"])
    missing = [i for i in range(n) if not (out / "c" / str(i) / "index.html").is_file()]
    if len(missing) == n:
        # a --skip-concepts preview build; everything else still has to be right
        globals()["PARTIAL"] = True
        print(f"  outputs   {len(required)} required files "
              f"(concept pages skipped — preview build)")
    elif missing:
        fail("outputs", f"{len(missing)} concept pages missing (first: {missing[:5]})")
        print(f"  outputs   {len(required)} required files + {n - len(missing):,} concept pages")
    else:
        print(f"  outputs   {len(required)} required files + {n:,} concept pages")


def check_json(out: Path):
    for p in sorted(out.rglob("*.json")) + [out / "manifest.webmanifest"]:
        try:
            json.loads(p.read_text("utf-8"))
        except Exception as exc:
            fail("json", f"{p.relative_to(out)} does not parse: {exc}")
    print(f"  json      {len(list(out.rglob('*.json')))} files parse")


def check_links(out: Path):
    have = {str(p.relative_to(out)).replace("\\", "/") for p in out.rglob("*") if p.is_file()}
    broken: dict[str, int] = {}
    checked = 0
    for page in out.rglob("*.html"):
        base = page.parent
        for raw in HREF.findall(page.read_text("utf-8")):
            if raw.startswith(SKIP) or not raw:
                continue
            target = unquote(urlparse(raw).path)
            if not target:
                continue
            resolved = (base / target).resolve() if not target.startswith("/") else (out / target.lstrip("/")).resolve()
            checked += 1
            try:
                rel = str(resolved.relative_to(out.resolve())).replace("\\", "/")
            except ValueError:
                broken.setdefault(f"{page.relative_to(out)} -> {raw} (escapes site root)", 0)
                broken[f"{page.relative_to(out)} -> {raw} (escapes site root)"] += 1
                continue
            if rel in have or f"{rel}/index.html".replace("//", "/") in have or f"{rel}index.html" in have:
                continue
            if PARTIAL and re.fullmatch(r"c/\d+", rel):
                continue   # preview build: concept pages were deliberately not generated
            if (resolved / "index.html").is_file() or resolved.is_file():
                continue
            key = f"{page.relative_to(out)} -> {raw}"
            broken[key] = broken.get(key, 0) + 1
    if broken:
        for k in list(broken)[:15]:
            fail("links", k)
        if len(broken) > 15:
            fail("links", f"... and {len(broken) - 15} more broken references")
    print(f"  links     {checked:,} internal references checked, {len(broken)} broken")


def check_sitemap(out: Path, kg):
    txt = (out / "sitemap-concepts.xml").read_text("utf-8")
    got = txt.count("<url>")
    want = len(kg["N"])
    if got != want and not PARTIAL:
        fail("sitemap", f"sitemap-concepts.xml lists {got} URLs, expected {want}")
    pages = (out / "sitemap-pages.xml").read_text("utf-8").count("<url>")
    print(f"  sitemap   {pages} pages + {got:,} concepts")


def main():
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "dist")
    if not out.is_dir():
        print(f"✗ {out} is not a directory — run scripts/build.py first")
        return 1
    print(f"checking {out} …")
    kg = check_source_data()
    check_outputs(out, kg)
    check_json(out)
    check_links(out)
    check_sitemap(out, kg)

    total = sum(p.stat().st_size for p in out.rglob("*") if p.is_file())
    print(f"  size      {total / 1024 / 1024:.1f} MB across "
          f"{sum(1 for p in out.rglob('*') if p.is_file()):,} files")

    if fails:
        print(f"\n✗ {len(fails)} problem(s):")
        for f in fails:
            print(f"   • {f}")
        return 1
    print("\n✓ all checks passed" + (" (preview build — concept pages not generated)" if PARTIAL else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
