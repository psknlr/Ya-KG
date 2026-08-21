#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ya-KG static site generator.

Reads  data/kg.json + data/vocab.json
Writes dist/  — a fully static, self-contained website:
       landing · explorer · glossary · parameters · chapters · study cards ·
       stats · about · 4882 pre-rendered concept pages · exports · sitemap · PWA

Stdlib only.  Usage:  python3 scripts/build.py [--base /Ya-KG/] [--out dist]
"""
from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import html
import io
import json
import os
import re
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
DATA = ROOT / "data"

REPO = os.environ.get("KG_REPO", "psknlr/Ya-KG")
SITE_URL = os.environ.get("KG_SITE_URL", "https://psknlr.github.io/Ya-KG").rstrip("/")

E = html.escape


def esc(s) -> str:
    return E(str(s if s is not None else ""), quote=True)


# ─────────────────────────────────────────────────────────────── load ──
def load():
    kg = json.loads((DATA / "kg.json").read_text("utf-8"))
    vocab = json.loads((DATA / "vocab.json").read_text("utf-8"))
    return kg, vocab


class Graph:
    """Derived views over the raw columnar arrays."""

    def __init__(self, kg, vocab):
        self.meta = kg["meta"]
        self.T = kg["T"]
        self.R = kg["R"]
        self.CH = kg["CH"]
        self.N = kg["N"]
        self.Ed = kg["E"]
        self.F = kg["F"]
        self.P = kg["P"]
        self.TZH = {k: v["zh"] for k, v in vocab["types"].items()}
        self.TEN = {k: v["en"] for k, v in vocab["types"].items()}
        self.TDESC = {k: v["desc"] for k, v in vocab["types"].items()}
        self.RZH = {k: v["zh"] for k, v in vocab["relations"].items()}
        self.RDESC = {k: v["desc"] for k, v in vocab["relations"].items()}

        n = len(self.N)
        self.out = [[] for _ in range(n)]
        self.inn = [[] for _ in range(n)]
        self.fct = [[] for _ in range(n)]
        self.prm = [[] for _ in range(n)]
        for k, (s, o, p, ev, inf) in enumerate(self.Ed):
            self.out[s].append(k)
            self.inn[o].append(k)
        for k, f in enumerate(self.F):
            self.fct[f[0]].append(k)
        for k, p in enumerate(self.P):
            self.prm[p[0]].append(k)
        self.deg = [len(self.out[i]) + len(self.inn[i]) for i in range(n)]
        self._rank_cache: dict[int, list[int]] = {}

    # ---- accessors -------------------------------------------------
    def name(self, i):
        return self.N[i][0]

    def tname(self, i):
        return self.T[self.N[i][2]]

    def tzh(self, i):
        t = self.tname(i)
        return self.TZH.get(t, t)

    def rzh(self, p):
        r = self.R[p]
        return self.RZH.get(r, r)

    def chapter_nodes(self, ch):
        return [i for i, r in enumerate(self.N) if ch in r[5]]

    def chapter_rank(self, ch):
        """Concepts of a chapter ordered by how central they are *within* it.

        Global degree alone surfaces the same book-wide hubs in every chapter,
        so score by edges whose both endpoints live in this chapter, and prefer
        concepts for which this chapter is the primary one."""
        if ch in self._rank_cache:
            return self._rank_cache[ch]
        ids = self.chapter_nodes(ch)
        member = set(ids)
        local = collections.Counter()
        for s_, o_, *_ in self.Ed:
            if s_ in member and o_ in member:
                local[s_] += 1
                local[o_] += 1
        ranked = sorted(ids, key=lambda i: (-(local[i] * 3
                                            + (6 if self.N[i][5][0] == ch else 0)
                                            + min(self.N[i][7], 20)
                                            + len(self.fct[i])),
                                            self.name(i)))
        self._rank_cache[ch] = ranked
        return ranked

    def components(self):
        n = len(self.N)
        parent = list(range(n))

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        for s, o, *_ in self.Ed:
            a, b = find(s), find(o)
            if a != b:
                parent[a] = b
        sizes = collections.Counter(find(i) for i in range(n))
        return sizes


# ─────────────────────────────────────────────────────── asset hashing ──
ASSET_V: dict[str, str] = {}


def digest(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()[:8]


def asset(rel: str, path: str) -> str:
    return f"{rel}assets/{path}?v={ASSET_V.get(path, '1')}"


# ───────────────────────────────────────────────────────────── layout ──
NAV = [
    ("", "首页", "概览与导航"),
    ("explorer/", "图谱浏览", "交互式关系网络"),
    ("chapters/", "章节导读", "按教材章节浏览"),
    ("glossary/", "术语表", "中英文对照"),
    ("parameters/", "临床参数", "定量标准速查"),
    ("cards/", "记忆卡片", "自测与复习"),
    ("stats/", "数据统计", "图谱结构分析"),
    ("about/", "关于", "方法与数据说明"),
]

MARK = (
    '<svg class="mark" viewBox="0 0 32 32" fill="none" aria-hidden="true">'
    '<circle cx="16" cy="7" r="4" fill="var(--acc)"/>'
    '<circle cx="6" cy="24" r="3.4" fill="var(--t-Prosthesis)"/>'
    '<circle cx="26" cy="24" r="3.4" fill="var(--t-Procedure)"/>'
    '<circle cx="16" cy="17.5" r="2.6" fill="var(--t-Anatomy)"/>'
    '<path d="M16 11v3.4M14 19.2 8.4 22.4M18 19.2l5.6 3.2M9 23h14" '
    'stroke="var(--ink-4)" stroke-width="1.3" stroke-linecap="round"/></svg>'
)

ICON_SEARCH = ('<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.7">'
               '<circle cx="9" cy="9" r="6"/><path d="m14 14 4 4" stroke-linecap="round"/></svg>')
ICON_SUN = ('<svg class="i-sun" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6">'
            '<circle cx="10" cy="10" r="3.6"/><path d="M10 2v2m0 12v2M2 10h2m12 0h2M4.6 4.6l1.4 1.4'
            'm8 8 1.4 1.4m0-10.8-1.4 1.4m-8 8-1.4 1.4" stroke-linecap="round"/></svg>')
ICON_MOON = ('<svg class="i-moon" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6">'
             '<path d="M16.5 12.4A7 7 0 0 1 7.6 3.5a7 7 0 1 0 8.9 8.9Z" stroke-linejoin="round"/></svg>')
ICON_GH = ('<svg viewBox="0 0 16 16" fill="currentColor"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 '
           '5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94'
           '-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87'
           '.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 '
           '2.2.82.64-.18 1.32-.27 2-.27s1.36.09 2 .27c1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51'
           '.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 '
           '.21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8Z"/></svg>')


def head_theme_script() -> str:
    return ("<script>(function(){try{var t=localStorage.getItem('kg-theme');"
            "if(t)document.documentElement.setAttribute('data-theme',t);}catch(e){}})()</script>")


NO_NAV = "\x00"          # sentinel: page belongs to no top-level nav item


def nav_html(rel: str, active: str, mobile=False) -> str:
    out = []
    for href, label, _ in NAV:
        cur = ' aria-current="page"' if href == active else ""
        out.append(f'<a href="{rel}{href}"{cur}>{label}</a>')
    return "".join(out)


def layout(*, depth: int, title: str, desc: str, body: str, active: str = NO_NAV,
           head: str = "", scripts: list[str] | None = None, canonical: str = "",
           jsonld: str = "", wide: bool = False, body_class: str = "") -> str:
    rel = "../" * depth if depth else "./"
    full_title = title if "Ya-KG" in title else f"{title} · Ya-KG"
    canon = f"{SITE_URL}/{canonical}" if canonical else SITE_URL + "/"
    scripts = scripts or []
    js = "".join(f'<script src="{asset(rel, s)}" defer></script>' for s in ["js/core.js"] + scripts)

    foot_links = "".join(f'<li><a href="{rel}{h}">{l}</a></li>' for h, l, _ in NAV[1:])
    return f"""<!doctype html>
<html lang="zh-Hans" data-base="{rel}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>{esc(full_title)}</title>
<meta name="description" content="{esc(desc)}">
<meta name="color-scheme" content="light dark">
<meta name="theme-color" content="#0d6e7a" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#0b1013" media="(prefers-color-scheme: dark)">
<link rel="canonical" href="{esc(canon)}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Ya-KG · 口腔修复学知识图谱">
<meta property="og:title" content="{esc(full_title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:url" content="{esc(canon)}">
<meta property="og:image" content="{SITE_URL}/assets/img/og.png">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="{rel}assets/img/favicon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="{rel}assets/img/icon-180.png">
<link rel="manifest" href="{rel}manifest.webmanifest">
<link rel="stylesheet" href="{asset(rel, 'css/app.css')}">
{head_theme_script()}
{head}
{f'<script type="application/ld+json">{jsonld}</script>' if jsonld else ''}
</head>
<body{f' class="{body_class}"' if body_class else ''}>
<a class="skip" href="#main">跳到主要内容</a>
<header class="site-head">
  <div class="page">
    <a class="brand" href="{rel}">{MARK}<span>Ya-KG<span class="sub">　口腔修复学知识图谱</span></span></a>
    <nav class="site-nav" aria-label="主导航">{nav_html(rel, active)}</nav>
    <div class="head-tools">
      <button class="searchbtn" data-palette aria-label="搜索概念">
        {ICON_SEARCH}<span>搜索概念…</span><kbd>⌘K</kbd>
      </button>
      <button class="iconbtn" data-theme-toggle aria-label="切换深浅色主题" title="切换主题">{ICON_SUN}{ICON_MOON}</button>
      <a class="iconbtn" href="https://github.com/{REPO}" rel="noopener" aria-label="GitHub 仓库" title="GitHub">{ICON_GH}</a>
    </div>
  </div>
</header>
<nav class="mobile-nav" aria-label="移动端导航"><div class="page">{nav_html(rel, active, True)}</div></nav>
<main id="main">
{body}
</main>
<footer class="site-foot">
  <div class="page">
    <div class="cols">
      <div>
        <div class="row" style="gap:8px;margin-bottom:9px">{MARK}<b style="color:var(--ink)">Ya-KG</b></div>
        <p style="max-width:32em;line-height:1.8">从《口腔修复学》（第 8 版，赵铱民主编 · 人民卫生出版社）
        自动抽取并人工校订的结构化知识图谱：4,882 个概念、9,242 条关系、5,458 条知识点、1,368 项定量临床参数。</p>
      </div>
      <div><h5>浏览</h5><ul>{foot_links}</ul></div>
      <div><h5>数据</h5><ul>
        <li><a href="{rel}data/kg.json">完整图谱 JSON</a></li>
        <li><a href="{rel}downloads/">全部导出格式</a></li>
        <li><a href="{rel}about/#schema">数据格式说明</a></li>
        <li><a href="https://github.com/{REPO}" rel="noopener">GitHub 仓库</a></li>
      </ul></div>
      <div><h5>项目</h5><ul>
        <li><a href="{rel}about/">方法与来源</a></li>
        <li><a href="{rel}about/#cite">如何引用</a></li>
        <li><a href="{rel}about/#license">许可与免责</a></li>
        <li><a href="https://github.com/{REPO}/issues" rel="noopener">反馈问题</a></li>
      </ul></div>
    </div>
    <div class="fine">
      内容源自受版权保护的教材，本项目仅提取事实性知识点用于<b>学习检索</b>，不替代教材与临床判断。
      代码以 MIT 许可发布，数据以 CC BY-NC-SA 4.0 发布。
      <br>本站为非官方学习工具，与出版社及原作者无隶属关系。临床决策请以最新教材、指南与执业规范为准。
    </div>
  </div>
</footer>
{js}
</body>
</html>
"""


# ═══════════════════════════════════════════════════════ concept pages ══
FACT_ORDER = ["定义", "分类", "适应证", "禁忌证", "步骤", "操作要点", "要求", "注意事项",
              "优点", "缺点", "材料性能", "数值标准", "并发症", "失败原因", "原因", "处理",
              "组成", "位置", "作用", "功能", "用途", "目的", "原理", "原则", "特点"]


def chip(g: Graph, i: int) -> str:
    t = g.tname(i)
    return f'<span class="chip-t" style="background:var(--t-{t})">{esc(g.TZH.get(t, t))}</span>'


def summarise(g: Graph, i: int) -> str:
    """Meta-description text for a concept."""
    n = g.N[i]
    bits = [f"{n[0]}"]
    if n[1]:
        bits.append(f"（{n[1]}）")
    bits.append(f"是《口腔修复学》第{'、'.join(map(str, n[5]))}章中的{g.tzh(i)}概念。")
    if n[3]:
        d = n[3]
        bits.append(d if len(d) <= 110 else d[:110] + "…")
    bits.append(f" 收录 {g.deg[i]} 条关系、{len(g.fct[i])} 条知识点。")
    return "".join(bits)[:300]


def rel_groups(g: Graph, keys: list[int], direction: str, cap: int = 6) -> str:
    if not keys:
        return ""
    groups: dict[int, list[int]] = collections.defaultdict(list)
    for k in keys:
        groups[g.Ed[k][2]].append(k)
    parts = []
    for p, ks in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        pred = g.R[p]
        rows = []
        for k in ks:
            s, o, _, ev, inf = g.Ed[k]
            other = o if direction == "out" else s
            rows.append(
                f'<div class="rel"><div class="hd">'
                f'<a href="../{other}/">{esc(g.name(other))}</a>{chip(g, other)}'
                + ('<span class="badge-inf" title="由同段落共现推断，无原文依据句">推断</span>' if inf else "")
                + "</div>"
                + (f'<div class="ev">{esc(ev)}</div>' if ev else "")
                + "</div>")
        head = (f'<div class="gh"><span class="pred">{esc(g.RZH.get(pred, pred))}</span>'
                f'<code>{esc(pred)}</code><span class="n">{len(ks)}</span></div>')
        if len(rows) > cap:
            visible = "".join(rows[:cap])
            hidden = "".join(rows[cap:])
            body = (visible + f'<details class="mt1"><summary class="small" style="cursor:pointer;color:var(--acc)">'
                    f'显示其余 {len(rows) - cap} 条</summary>{hidden}</details>')
        else:
            body = "".join(rows)
        parts.append(f'<div class="rel-grp">{head}{body}</div>')
    label = "出向关系" if direction == "out" else "入向关系"
    return (f'<div class="sec-title">{label}<span class="n">{len(keys)}</span></div>' + "".join(parts))


def concept_page(g: Graph, i: int) -> str:
    n = g.N[i]
    name, en, t, definition, aliases, chapters, pages, mentions = n
    tname = g.T[t]

    facts: dict[str, list] = collections.defaultdict(list)
    for k in g.fct[i]:
        f = g.F[k]
        facts[f[1] or "要点"].append(f)
    keys = [k for k in FACT_ORDER if k in facts] + [k for k in facts if k not in FACT_ORDER]

    crumb = ('<div class="crumb"><a href="../../">首页</a><span class="sep">›</span>'
             + '<a href="../../chapters/">章节</a><span class="sep">›</span>'
             + f'<a href="../../chapters/{chapters[0]}/">第{chapters[0]}章 {esc(g.CH[str(chapters[0])])}</a>'
             + f'<span class="sep">›</span><span>{esc(name)}</span></div>')

    head = (f'<div class="chead"><h1>{esc(name)}{chip(g, i)}</h1>'
            + (f'<div class="en">{esc(en)}</div>' if en else "")
            + '<div class="m">'
            + f'第{"、".join(map(str, chapters))}章<span class="sep">·</span>'
            + f'p{", ".join(map(str, pages[:10]))}<span class="sep">·</span>'
            + f'{g.deg[i]} 关系<span class="sep">·</span>{len(g.fct[i])} 知识点'
            + (f'<span class="sep">·</span>{len(g.prm[i])} 参数' if g.prm[i] else "")
            + f'<span class="sep">·</span>全文提及 {mentions} 次</div></div>')

    body = [crumb, head]
    if definition:
        body.append(f'<div class="def-box">{esc(definition)}</div>')
    if aliases:
        body.append('<div class="alias-row">'
                    + "".join(f'<span class="pill">{esc(a)}</span>' for a in aliases) + "</div>")

    if g.prm[i]:
        body.append(f'<div class="sec-title">定量参数<span class="n">{len(g.prm[i])}</span></div>')
        for k in g.prm[i]:
            _, pn, pv, pu, pc, ppg = g.P[k]
            body.append(f'<div class="prm"><span class="pn">{esc(pn)}</span>'
                        f'<span class="pv">{esc(pv)}{esc(pu)}</span>'
                        + (f'<span class="pc">{esc(pc)}</span>' if pc else "")
                        + f'<span class="pg">p{ppg}</span></div>')

    for key in keys:
        rows = facts[key]
        body.append(f'<div class="sec-title">{esc(key)}<span class="n">{len(rows)}</span></div><ul class="facts">'
                    + "".join(f'<li>{esc(f[2])}<span class="pg">p{f[3]}</span></li>' for f in rows) + "</ul>")

    body.append(rel_groups(g, g.out[i], "out"))
    body.append(rel_groups(g, g.inn[i], "in"))

    # ---- aside --------------------------------------------------------
    nbrs = []
    seen = set()
    for k in g.out[i]:
        o = g.Ed[k][1]
        if o not in seen:
            seen.add(o)
            nbrs.append((o, g.name(o), g.tname(o), 1))
    for k in g.inn[i]:
        s = g.Ed[k][0]
        if s not in seen:
            seen.add(s)
            nbrs.append((s, g.name(s), g.tname(s), 0))
    nbrs.sort(key=lambda x: -g.deg[x[0]])
    nbr_map = nbrs[:26]

    same_type = sorted((j for j in range(len(g.N))
                        if g.N[j][2] == t and j != i and set(g.N[j][5]) & set(chapters)),
                       key=lambda j: -(g.deg[j] + g.N[j][7]))[:6]
    same_chap = [j for j in g.chapter_rank(chapters[0]) if j != i][:6]

    aside = ['<aside class="aside">']
    aside.append('<div class="box"><h4>概览</h4>'
                 + f'<div class="kv"><span class="k">类型</span><span class="v">{esc(g.TZH.get(tname, tname))}</span></div>'
                 + f'<div class="kv"><span class="k">连接度</span><span class="v">{g.deg[i]}</span></div>'
                 + f'<div class="kv"><span class="k">出向 / 入向</span><span class="v">{len(g.out[i])} / {len(g.inn[i])}</span></div>'
                 + f'<div class="kv"><span class="k">知识点</span><span class="v">{len(g.fct[i])}</span></div>'
                 + f'<div class="kv"><span class="k">定量参数</span><span class="v">{len(g.prm[i])}</span></div>'
                 + f'<div class="kv"><span class="k">同义词</span><span class="v">{len(aliases)}</span></div>'
                 + f'<div class="kv"><span class="k">出处页码</span><span class="v">p{", ".join(map(str, pages[:6]))}</span></div>'
                 + '</div>')
    if nbr_map:
        payload = json.dumps({"c": [name, tname],
                              "n": [[x[0], x[1], x[2], x[3]] for x in nbr_map]},
                             ensure_ascii=False, separators=(",", ":"))
        aside.append('<div class="box" id="minimapBox"><h4>邻域关系图</h4>'
                     '<canvas class="minimap" id="minimap" aria-label="邻域关系示意图"></canvas>'
                     '<p class="tiny dimmer mt1">右侧为出向、左侧为入向；点击节点跳转。'
                     f'<a href="../../explorer/?n={i}">在完整浏览器中打开 ↗</a></p>'
                     f'<script type="application/json" id="nbrdata">{payload}</script></div>')
    if same_type:
        aside.append('<div class="box"><h4>同类型相关概念</h4>'
                     + "".join(f'<a class="nb" href="../{j}/">{esc(g.name(j))}'
                               f'<small>{g.deg[j]} 关系</small></a>' for j in same_type) + "</div>")
    if same_chap:
        aside.append(f'<div class="box"><h4>第{chapters[0]}章核心概念</h4>'
                     + "".join(f'<a class="nb" href="../{j}/">{esc(g.name(j))}'
                               f'<small>{g.deg[j]} 关系</small></a>' for j in same_chap)
                     + f'<a class="nb" href="../../chapters/{chapters[0]}/" style="color:var(--acc)">'
                       f'查看本章全部 →</a></div>')
    cite = (f"{name}（{en}）. Ya-KG · 口腔修复学知识图谱. "
            f"源自《口腔修复学》第8版, 赵铱民主编, 人民卫生出版社, p{', '.join(map(str, pages[:4]))}. "
            f"{SITE_URL}/c/{i}/")
    aside.append('<div class="box"><h4>操作</h4><div class="stack" style="gap:7px">'
                 f'<a class="btn sm" href="../../explorer/?n={i}">在图谱浏览器中打开</a>'
                 f'<button class="btn sm ghost" data-copy="{esc(cite)}" data-copy-label="引用信息已复制">复制引用信息</button>'
                 f'<a class="btn sm ghost" href="../../downloads/">下载完整数据集</a>'
                 "</div></div>")
    aside.append("</aside>")

    jsonld = json.dumps({
        "@context": "https://schema.org",
        "@type": "DefinedTerm",
        "name": name,
        "alternateName": ([en] if en else []) + list(aliases),
        "description": definition or summarise(g, i),
        "inDefinedTermSet": {
            "@type": "DefinedTermSet",
            "name": "口腔修复学知识图谱 (Ya-KG)",
            "url": SITE_URL + "/",
        },
        "url": f"{SITE_URL}/c/{i}/",
        "termCode": str(i),
        "inLanguage": "zh-Hans",
    }, ensure_ascii=False, separators=(",", ":"))

    inner = f'<div class="page"><div class="concept"><article>{"".join(body)}</article>{"".join(aside)}</div></div>'
    return layout(depth=2, title=f"{name}{f' {en}' if en else ''}", desc=summarise(g, i),
                  body=inner, canonical=f"c/{i}/", jsonld=jsonld,
                  scripts=["js/concept.js"])


# ══════════════════════════════════════════════════════════ static pages ══
def icon(path: str) -> str:
    return f'<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">{path}</svg>'


I_GRAPH = icon('<circle cx="10" cy="4" r="2.2"/><circle cx="4" cy="15" r="2.2"/><circle cx="16" cy="15" r="2.2"/><path d="M10 6.2 5.2 13M10 6.2 14.8 13M6.2 15h7.6"/>')
I_BOOK = icon('<path d="M3 4.5A1.5 1.5 0 0 1 4.5 3H9v14H4.5A1.5 1.5 0 0 1 3 15.5ZM17 4.5A1.5 1.5 0 0 0 15.5 3H11v14h4.5a1.5 1.5 0 0 0 1.5-1.5Z"/>')
I_ABC = icon('<path d="M2.5 15 6 5l3.5 10M3.6 12h4.8M12 15V5h2.6a2.5 2.5 0 0 1 0 5H12m0 0h3.1a2.5 2.5 0 0 1 0 5H12"/>')
I_RULER = icon('<rect x="2" y="6.5" width="16" height="7" rx="1.4"/><path d="M6 6.5v3M10 6.5v4M14 6.5v3"/>')
I_CARD = icon('<rect x="2.5" y="4" width="15" height="12" rx="2"/><path d="M6 8h8M6 11.5h5"/>')
I_CHART = icon('<path d="M3 16.5h14M6 13V8M10 13V4.5M14 13v-3.5"/>')
I_DOWN = icon('<path d="M10 3v10m0 0 3.4-3.4M10 13 6.6 9.6M3.5 16.5h13"/>')
I_CODE = icon('<path d="M7 6 3 10l4 4M13 6l4 4-4 4"/>')


def landing(g: Graph) -> str:
    m = g.meta
    hubs = sorted(range(len(g.N)), key=lambda i: -g.deg[i])[:12]
    type_counts = collections.Counter(r[2] for r in g.N)
    ch_counts = {k: len(g.chapter_nodes(int(k))) for k in g.CH}
    ch_facts = collections.Counter()
    for f in g.F:
        for c in g.N[f[0]][5]:
            ch_facts[c] += 1
    ch_params = collections.Counter()
    for p in g.P:
        for c in g.N[p[0]][5]:
            ch_params[c] += 1

    stat = lambda v, l: f'<div class="s"><b>{v:,}</b><span>{l}</span></div>'
    statbar = ('<div class="statbar">'
               + stat(m["n"], "实体概念")
               + stat(m["e"], "关系三元组")
               + stat(m["f"], "结构化知识点")
               + stat(m["p"], "定量临床参数")
               + stat(m["g"], "中英术语对照")
               + "</div>")

    feats = [
        ("explorer/", I_GRAPH, "图谱浏览器",
         "以任意概念为中心展开 1–3 跳邻域，力导向布局实时呈现 9,242 条关系；支持按类型筛选、导出子图 PNG。"),
        ("chapters/", I_BOOK, "章节导读",
         "对齐教材 10 个章节，逐章列出核心概念、知识点与本章专属的临床参数，复习时按章推进。"),
        ("glossary/", I_ABC, "中英术语表",
         f"{m['g']:,} 条中英文对照术语，可按首字母、类型与章节筛选，一键导出 CSV。"),
        ("parameters/", I_RULER, "临床参数速查",
         f"{m['p']:,} 项带数值的临床标准——肩台宽度、聚合度、瓷层厚度、就位道角度……考前速记的硬通货。"),
        ("cards/", I_CARD, "记忆卡片",
         "四种题型（术语→释义 / 释义→术语 / 中→英 / 参数速记）+ 间隔重复排程，进度保存在本机。"),
        ("stats/", I_CHART, "数据统计",
         "实体与关系分布、章节密度、枢纽概念、证据覆盖率——先看清图谱形状，再决定从哪里读起。"),
    ]
    feat_html = "".join(
        f'<a class="card feat" href="{h}"><div class="ico">{ic}</div><h3>{t}</h3><p>{d}</p></a>'
        for h, ic, t, d in feats)

    def spark(ch: int) -> str:
        c = collections.Counter(g.N[i][2] for i in g.chapter_nodes(ch))
        tot = sum(c.values()) or 1
        return "".join(f'<i style="width:{v / tot * 100:.1f}%;background:var(--t-{g.T[k]})"></i>'
                       for k, v in c.most_common())

    chap_html = "".join(
        f'<a class="card chap" href="chapters/{k}/"><span class="num">{k}</span>'
        f'<div style="min-width:0"><h4>{esc(v)}</h4>'
        f'<div class="m">{ch_counts[k]} 概念 · {ch_facts[int(k)]} 知识点'
        + (f' · {ch_params[int(k)]} 参数' if ch_params[int(k)] else "")
        + f'</div><div class="spark">{spark(int(k))}</div></div></a>'
        for k, v in g.CH.items())

    hub_html = "".join(
        f'<a class="card pad" href="c/{i}/" style="padding:13px 15px">'
        f'<div class="row tight" style="gap:6px"><b style="font-size:14.5px">{esc(g.name(i))}</b>{chip(g, i)}</div>'
        + (f'<div class="tiny dim truncate" style="font-style:italic;margin-top:2px">{esc(g.N[i][1])}</div>' if g.N[i][1] else "")
        + f'<div class="tiny dimmer mt1">{g.deg[i]} 关系 · {len(g.fct[i])} 知识点</div></a>'
        for i in hubs)

    type_html = "".join(
        f'<a class="pill" href="explorer/" style="border-color:var(--t-{g.T[k]})">'
        f'<span class="dot" style="background:var(--t-{g.T[k]})"></span>'
        f'{esc(g.TZH.get(g.T[k], g.T[k]))}<b style="color:var(--ink-3);font-weight:600">{v}</b></a>'
        for k, v in type_counts.most_common())

    body = f"""
<div class="page">
  <section class="hero">
    <span class="eyebrow">📘 《口腔修复学》第 8 版 · 赵铱民主编 · 人民卫生出版社</span>
    <h1>把一本教材，读成一张可以走进去的知识网络</h1>
    <p class="lede">Ya-KG 将《口腔修复学》第 8 版全书（p12–p391）拆解为
      <b>{g.meta['n']:,} 个概念</b>、<b>{g.meta['e']:,} 条带原文依据的关系</b>与
      <b>{g.meta['p']:,} 项定量临床参数</b>，每条知识点都可回溯到具体页码。
      检索、串联、自测，全部在浏览器中完成——无需安装，数据完全开放。</p>
    <div class="cta">
      <a class="btn primary" href="explorer/">{I_GRAPH} 进入图谱浏览器</a>
      <button class="btn" data-palette>{ICON_SEARCH} 搜索一个概念 <kbd>⌘K</kbd></button>
      <a class="btn" href="about/">了解构建方法</a>
    </div>
    {statbar}
    <p class="tiny dimmer">抽取模型 {esc(g.meta['model'])} · 覆盖 {esc(g.meta['pages'])} ·
      {g.meta['ext']:,} 条关系带原文依据句（{g.meta['ext'] / g.meta['e'] * 100:.1f}%）·
      {g.meta['inf']:,} 条为同段落共现推断并已标注</p>
  </section>

  <section class="mt4">
    <div class="spread mb2"><h2>六种进入方式</h2>
      <span class="small dim">同一份数据，六个视角</span></div>
    <div class="grid c3">{feat_html}</div>
  </section>

  <section class="mt4">
    <div class="spread mb2"><h2>按章节浏览</h2>
      <a class="small" href="chapters/">全部章节 →</a></div>
    <div class="grid c2">{chap_html}</div>
  </section>

  <section class="mt4">
    <div class="spread mb2"><h2>连接最密集的概念</h2>
      <span class="small dim">按连接度排序，通常是全书的骨架</span></div>
    <div class="grid auto">{hub_html}</div>
  </section>

  <section class="mt4">
    <div class="spread mb2"><h2>14 类实体</h2>
      <a class="small" href="stats/">完整统计 →</a></div>
    <div class="row tight">{type_html}</div>
  </section>

  <section class="mt4">
    <div class="grid c2">
      <div class="card pad">
        <div class="row tight mb1">{I_DOWN}<h3 style="margin:0">数据开放，随手可取</h3></div>
        <p class="small dim">完整图谱以 JSON 发布，另提供 CSV、JSON-Lines、Neo4j Cypher 与 RDF/Turtle 导出，
          可直接导入 Neo4j、Obsidian、Anki 或自建检索系统。</p>
        <div class="row tight mt2">
          <a class="btn sm" href="downloads/">全部下载</a>
          <a class="btn sm ghost" href="data/kg.json">kg.json</a>
          <a class="btn sm ghost" href="about/#schema">格式说明</a>
        </div>
      </div>
      <div class="card pad">
        <div class="row tight mb1">{I_CODE}<h3 style="margin:0">三行代码开始用</h3></div>
        <pre style="margin-top:8px"><code>import json, urllib.request
u = "{SITE_URL}/data/kg.json"
kg = json.load(urllib.request.urlopen(u))
print(kg["meta"], len(kg["N"]), "concepts")</code></pre>
      </div>
    </div>
  </section>

  <section class="mt4 mb3">
    <div class="note warm"><b>使用提示　</b>本站是学习检索工具，不是临床指南。
      知识点均为教材原文的结构化重述，抽取过程可能存在遗漏或偏差；
      标注为「推断」的关系没有直接原文依据句，请以教材为准。发现问题欢迎在
      <a href="https://github.com/{REPO}/issues" rel="noopener">GitHub Issues</a> 反馈。</div>
  </section>
</div>
"""
    return layout(depth=0, title="Ya-KG · 口腔修复学知识图谱", active="",
                  desc=f"《口腔修复学》第8版结构化知识图谱：{g.meta['n']:,} 个概念、{g.meta['e']:,} 条关系、"
                       f"{g.meta['p']:,} 项定量临床参数，全部可回溯页码。交互式图谱浏览、术语表、参数速查与记忆卡片。",
                  body=body, canonical="",
                  jsonld=json.dumps({
                      "@context": "https://schema.org",
                      "@type": "Dataset",
                      "name": "Ya-KG · 口腔修复学知识图谱",
                      "description": f"Structured knowledge graph extracted from 口腔修复学 (Prosthodontics), 8th edition. "
                                     f"{g.meta['n']} entities, {g.meta['e']} relations, {g.meta['p']} clinical parameters.",
                      "url": SITE_URL + "/",
                      "inLanguage": ["zh-Hans", "en"],
                      "license": "https://creativecommons.org/licenses/by-nc-sa/4.0/",
                      "creator": {"@type": "Organization", "name": "Ya-KG"},
                      "distribution": [
                          {"@type": "DataDownload", "encodingFormat": "application/json",
                           "contentUrl": SITE_URL + "/data/kg.json"},
                          {"@type": "DataDownload", "encodingFormat": "text/csv",
                           "contentUrl": SITE_URL + "/downloads/kg-entities.csv"},
                      ],
                      "keywords": ["口腔修复学", "prosthodontics", "knowledge graph", "dentistry", "知识图谱"],
                  }, ensure_ascii=False, separators=(",", ":")))


def chapters_index(g: Graph) -> str:
    ch_facts = collections.Counter()
    for f in g.F:
        for c in g.N[f[0]][5]:
            ch_facts[c] += 1
    ch_params = collections.Counter()
    for p in g.P:
        for c in g.N[p[0]][5]:
            ch_params[c] += 1

    cards = []
    for k, v in g.CH.items():
        ids = g.chapter_nodes(int(k))
        top = g.chapter_rank(int(k))[:8]
        tc = collections.Counter(g.N[i][2] for i in ids)
        tot = sum(tc.values()) or 1
        spark = "".join(f'<i style="width:{c / tot * 100:.1f}%;background:var(--t-{g.T[t]})"></i>'
                        for t, c in tc.most_common())
        cards.append(
            f'<div class="card pad"><div class="spread mb1">'
            f'<h3 style="margin:0"><a href="{k}/">第{k}章　{esc(v)}</a></h3>'
            f'<span class="pill">{len(ids)} 概念</span></div>'
            f'<div class="spark" style="display:flex;gap:2px;height:5px;border-radius:999px;overflow:hidden;'
            f'background:var(--surface-3);margin-bottom:10px">{spark}</div>'
            f'<div class="tiny dim mb2">{ch_facts[int(k)]} 知识点 · {ch_params[int(k)]} 定量参数 · '
            f'{sum(g.deg[i] for i in ids) // 2} 关系</div>'
            + '<div class="row tight">'
            + "".join(f'<a class="pill" href="../c/{i}/">{esc(g.name(i))}</a>' for i in top)
            + f'</div><div class="mt2"><a class="btn sm" href="{k}/">进入本章 →</a></div></div>')

    body = f"""
<div class="page pt3">
  <h1>章节导读</h1>
  <p class="lede small dim mt1" style="max-width:44em">图谱与教材的 10 个章节严格对齐。
  概念可跨章出现（例如「基牙」在第 4、5、7 章均有讨论），因此各章概念数之和大于实体总数。</p>
  <div class="grid c2 mt3">{"".join(cards)}</div>
</div>
"""
    return layout(depth=1, title="章节导读", active="chapters/", canonical="chapters/",
                  desc="按《口腔修复学》第8版的 10 个章节浏览知识图谱：各章概念、知识点、定量参数与核心术语。",
                  body=body)


def chapter_page(g: Graph, ch: int) -> str:
    name = g.CH[str(ch)]
    ids = g.chapter_nodes(ch)
    by_type: dict[int, list[int]] = collections.defaultdict(list)
    for i in ids:
        by_type[g.N[i][2]].append(i)
    facts = [k for k, f in enumerate(g.F) if ch in g.N[f[0]][5]]
    params = [k for k, p in enumerate(g.P) if ch in g.N[p[0]][5]]
    top = g.chapter_rank(ch)[:12]

    top_html = "".join(
        f'<a class="card pad" href="../../c/{i}/" style="padding:13px 15px">'
        f'<div class="row tight" style="gap:6px"><b style="font-size:14.5px">{esc(g.name(i))}</b>{chip(g, i)}</div>'
        + (f'<div class="tiny dim truncate" style="font-style:italic;margin-top:2px">{esc(g.N[i][1])}</div>' if g.N[i][1] else "")
        + (f'<div class="small dim mt1" style="line-height:1.6;display:-webkit-box;-webkit-line-clamp:2;'
           f'-webkit-box-orient:vertical;overflow:hidden">{esc(g.N[i][3])}</div>' if g.N[i][3] else "")
        + f'<div class="tiny dimmer mt1">{g.deg[i]} 关系 · {len(g.fct[i])} 知识点</div></a>'
        for i in top)

    groups = []
    for t, lst in sorted(by_type.items(), key=lambda kv: -len(kv[1])):
        tn = g.T[t]
        order = {v: k for k, v in enumerate(g.chapter_rank(ch))}
        lst = sorted(lst, key=lambda i: order.get(i, 1 << 30))
        groups.append(
            f'<div class="sec-title"><span class="dot" style="background:var(--t-{tn})"></span>'
            f'{esc(g.TZH.get(tn, tn))}<span class="n">{len(lst)}</span></div>'
            '<div class="row tight" style="gap:5px">'
            + "".join(f'<a class="pill" href="../../c/{i}/" title="{esc(g.N[i][3][:80])}">{esc(g.name(i))}'
                      + (f'<b style="color:var(--ink-4);font-weight:500">{g.deg[i]}</b>' if g.deg[i] else "")
                      + "</a>" for i in lst)
            + "</div>")

    param_rows = "".join(
        f'<tr><td><a href="../../c/{g.P[k][0]}/">{esc(g.name(g.P[k][0]))}</a></td>'
        f'<td>{esc(g.P[k][1])}</td><td class="nowrap"><span class="prm-v">{esc(g.P[k][2])}{esc(g.P[k][3])}</span></td>'
        f'<td class="small dim">{esc(g.P[k][4])}</td><td class="tiny dimmer">p{g.P[k][5]}</td></tr>'
        for k in sorted(params, key=lambda k: g.P[k][5]))
    param_block = (f'<h2 class="mt4">本章定量参数<span class="pill" style="margin-left:9px">{len(params)}</span></h2>'
                   '<div class="table-wrap mt2"><table><thead><tr><th>概念</th><th>参数</th><th>数值</th>'
                   f'<th>适用条件</th><th>页</th></tr></thead><tbody>{param_rows}</tbody></table></div>'
                   ) if params else ""

    prev_next = []
    if ch > 1:
        prev_next.append(f'<a class="btn sm" href="../{ch - 1}/">← 第{ch - 1}章 {esc(g.CH[str(ch - 1)])}</a>')
    if str(ch + 1) in g.CH:
        prev_next.append(f'<a class="btn sm" href="../{ch + 1}/">第{ch + 1}章 {esc(g.CH[str(ch + 1)])} →</a>')

    body = f"""
<div class="page pt3">
  <div class="crumb"><a href="../../">首页</a><span class="sep">›</span>
    <a href="../">章节导读</a><span class="sep">›</span><span>第{ch}章</span></div>
  <div class="spread">
    <div><h1>第{ch}章　{esc(name)}</h1>
      <p class="m small dim mt1">{len(ids)} 个概念 · {len(facts)} 条知识点 · {len(params)} 项定量参数</p></div>
    <a class="btn" href="../../explorer/?n={top[0] if top else 0}">在图谱中打开</a>
  </div>

  <h2 class="mt3">核心概念</h2>
  <div class="grid auto mt2">{top_html}</div>

  <h2 class="mt4">本章全部概念</h2>
  <p class="small dim">按类型分组，组内按重要度排序；数字为该概念的关系数。</p>
  {"".join(groups)}

  {param_block}

  <div class="row mt4 mb3">{"".join(prev_next)}</div>
</div>
"""
    return layout(depth=2, title=f"第{ch}章 {name}", active="chapters/", canonical=f"chapters/{ch}/",
                  desc=f"《口腔修复学》第8版第{ch}章「{name}」知识图谱：{len(ids)} 个概念、"
                       f"{len(facts)} 条知识点、{len(params)} 项定量临床参数。",
                  body=body)


def explorer_page(g: Graph) -> str:
    body = """
<div class="explorer" id="explorer" data-pane="graph">
  <div class="ex-tabs" role="tablist">
    <button data-pane="list" role="tab" aria-selected="false">列表</button>
    <button data-pane="graph" role="tab" aria-selected="true">图谱</button>
    <button data-pane="detail" role="tab" aria-selected="false">详情</button>
  </div>

  <div class="ex-side">
    <div class="box">
      <input type="search" id="q" class="field" placeholder="搜索概念 / 英文 / 同义词 / 定义…" aria-label="搜索概念">
    </div>
    <div class="box">
      <select id="ch" class="field" aria-label="按章节筛选"></select>
    </div>
    <div class="box">
      <div class="lbl">实体类型 <button id="tall" type="button">全选</button></div>
      <div class="row tight" id="tchips" style="gap:4px"></div>
    </div>
    <div class="box" style="display:flex;align-items:center;justify-content:space-between">
      <span class="tiny dim" id="cnt">—</span>
      <label class="tiny dim row tight" style="gap:5px;cursor:pointer">
        <input type="checkbox" id="infTgl"> 隐藏推断关系
      </label>
    </div>
    <div class="ex-list" id="hits" role="listbox" aria-label="概念列表"></div>
  </div>

  <div class="ex-canvas">
    <canvas id="cv"></canvas>
    <div class="ex-hud">
      <span class="h" id="exState">初始化…</span>
      <span class="h" id="gmeta"></span>
    </div>
    <div class="ex-ctl">
      <div class="g"><label for="hops">展开</label>
        <select id="hops" class="field" style="width:auto">
          <option value="1" selected>1 跳</option><option value="2">2 跳</option><option value="3">3 跳</option>
        </select></div>
      <div class="g">
        <button id="refit" type="button" title="快捷键 F">适应窗口</button>
        <button id="relayout" type="button" title="快捷键 R">重新布局</button>
        <button id="png" type="button">导出 PNG</button>
      </div>
      <div class="g tiny dimmer hint-row">拖拽平移 · 滚轮缩放 · 点击节点跳转</div>
    </div>
    <div class="ex-legend" id="legend"></div>
    <div class="ex-tip" id="tip"></div>
  </div>

  <div class="ex-det" id="det"><div class="empty">正在载入…</div></div>
</div>
"""
    return layout(depth=1, title="图谱浏览器", active="explorer/", canonical="explorer/",
                  desc="交互式知识图谱浏览器：以任意概念为中心展开 1–3 跳关系邻域，力导向布局呈现"
                       "《口腔修复学》第8版的 9,242 条关系，支持类型筛选与子图导出。",
                  body=body, scripts=["js/explorer.js"], wide=True,
                  head='<style>body{overflow:hidden}main{overflow:hidden}.site-foot{display:none}</style>')


def glossary_page(g: Graph) -> str:
    body = f"""
<div class="page pt3">
  <div class="spread">
    <div><h1>中英术语对照表</h1>
      <p class="small dim mt1" style="max-width:44em">{g.meta['g']:,} 条术语，覆盖全书 14 类实体。
      可按中文名、英文名检索，按英文首字母、实体类型与章节筛选，筛选结果可直接导出 CSV。</p></div>
    <button class="btn" id="glCsv">导出当前结果 CSV</button>
  </div>

  <div class="card pad mt3">
    <div class="grid c3" style="gap:12px">
      <input type="search" id="glQ" class="field" placeholder="搜索中文或英文术语…" aria-label="搜索术语">
      <select id="glCh" class="field" aria-label="按章节筛选"></select>
      <div class="row tight small dim" style="justify-content:flex-end">
        共 <b id="glCount">—</b> 条结果
      </div>
    </div>
    <div class="mt2"><div class="lbl tiny dimmer mb1">英文首字母</div>
      <div class="row tight" id="glAlpha" style="gap:3px"></div></div>
    <div class="mt2"><div class="lbl tiny dimmer mb1">实体类型</div>
      <div class="row tight" id="glTypes" style="gap:4px"></div></div>
  </div>

  <div id="glState" class="empty">正在载入术语表…</div>
  <div class="table-wrap mt3" id="gl">
    <table>
      <thead><tr>
        <th class="sortable" data-key="name" style="width:26%">中文</th>
        <th class="sortable" data-key="en" style="width:36%">English</th>
        <th class="sortable" data-key="type" style="width:14%">类型</th>
        <th style="width:24%">出处</th>
      </tr></thead>
      <tbody></tbody>
    </table>
  </div>
  <div class="center mt2 mb3"><button class="btn" id="glMore" hidden></button></div>
</div>
"""
    return layout(depth=1, title="中英术语表", active="glossary/", canonical="glossary/",
                  desc=f"《口腔修复学》第8版中英文术语对照表，共 {g.meta['g']:,} 条，"
                       "按类型与章节筛选，支持 CSV 导出。",
                  body=body, scripts=["js/glossary.js"])


def parameters_page(g: Graph) -> str:
    units = collections.Counter(p[3] for p in g.P)
    body = f"""
<div class="page pt3">
  <div class="spread">
    <div><h1>定量临床参数速查</h1>
      <p class="small dim mt1" style="max-width:46em">教材中所有带数值的临床标准——预备体聚合度、肩台宽度、
      瓷层厚度、基托厚度、烤瓷温度、种植体间距……共 <b>{g.meta['p']:,}</b> 项，
      每项标注适用条件与出处页码。这是考前与椅旁最常查的一张表。</p></div>
    <button class="btn" id="ptCsv">导出当前结果 CSV</button>
  </div>

  <div class="card pad mt3">
    <div class="grid c3" style="gap:12px">
      <input type="search" id="ptQ" class="field" placeholder="搜索概念、参数名、数值或条件…" aria-label="搜索参数">
      <select id="ptCh" class="field" aria-label="按章节筛选"></select>
      <select id="ptUnit" class="field" aria-label="按单位筛选"></select>
    </div>
    <div class="row tight small dim mt2">共 <b id="ptCount">—</b> 项参数
      <span class="dimmer tiny" style="margin-left:auto">点击表头可排序</span></div>
  </div>

  <div id="ptState" class="empty">正在载入参数表…</div>
  <div class="table-wrap mt3" id="pt">
    <table>
      <thead><tr>
        <th class="sortable" data-key="ent" style="width:22%">概念</th>
        <th class="sortable" data-key="n" style="width:18%">参数</th>
        <th class="sortable" data-key="v" style="width:13%">数值</th>
        <th style="width:38%">适用条件</th>
        <th class="sortable" data-key="pg" style="width:9%">页</th>
      </tr></thead>
      <tbody></tbody>
    </table>
  </div>
  <div class="center mt2 mb3"><button class="btn" id="ptMore" hidden></button></div>

  <div class="note warm mb3"><b>注意　</b>参数为教材原文的抽取结果，单位与区间按原文保留
    （共 {len(units)} 种量纲，其中 mm {units.get('mm', 0)} 项、° {units.get('°', 0)} 项）。
    临床应用请核对教材原文与最新指南。</div>
</div>
"""
    return layout(depth=1, title="定量临床参数", active="parameters/", canonical="parameters/",
                  desc=f"《口腔修复学》第8版 {g.meta['p']:,} 项定量临床参数速查表："
                       "肩台宽度、聚合度、瓷层厚度、就位道角度等，含适用条件与页码，可排序与导出。",
                  body=body, scripts=["js/parameters.js"])


def cards_page(g: Graph) -> str:
    ch_json = json.dumps(g.CH, ensure_ascii=False, separators=(",", ":"))
    body = f"""
<div class="page pt3">
  <div class="center mb3">
    <h1>记忆卡片</h1>
    <p class="small dim mt1" style="max-width:40em;margin-inline:auto">四种题型 + 间隔重复排程。
      标记为「掌握」的卡片会按 1 / 3 / 7 / 16 / 35 / 70 天的间隔推迟出现，
      进度保存在你的浏览器本机，不会上传。</p>
  </div>

  <div class="deck">
    <div class="card pad mb3">
      <div class="grid c3" style="gap:12px">
        <select id="cmMode" class="field" aria-label="题型">
          <option value="def">术语 → 释义与要点</option>
          <option value="rev">释义 → 术语</option>
          <option value="en">中文 → English</option>
          <option value="param">参数速记</option>
        </select>
        <select id="cmCh" class="field" aria-label="章节"></select>
        <div class="row tight" style="justify-content:flex-end">
          <button class="btn sm ghost" id="cmRestart">重新开始</button>
          <button class="btn sm ghost" id="cmReset">清除进度</button>
        </div>
      </div>
    </div>

    <div id="cardBox"><div class="empty">正在准备卡片…</div></div>

    <div class="progress"><i id="prog" style="width:0"></i></div>
    <div class="deck-bar">
      <span class="small dim" id="cardMeta">—</span>
    </div>
    <div class="deck-bar" id="gradeRow" hidden>
      <button class="btn" id="gradeNo">还不熟 <kbd>1</kbd></button>
      <button class="btn primary" id="gradeOk">已掌握 <kbd>2</kbd></button>
    </div>
    <p class="center tiny dimmer mt2 mb3">
      <kbd>空格</kbd> 翻面　<kbd>←</kbd> <kbd>→</kbd> 前后翻页　<kbd>1</kbd>/<kbd>2</kbd> 评分　<kbd>R</kbd> 重开
    </p>
  </div>
</div>
<script>window.KG_CH={ch_json};</script>
"""
    return layout(depth=1, title="记忆卡片", active="cards/", canonical="cards/",
                  desc="基于《口腔修复学》知识图谱的记忆卡片自测：术语释义、中英互译与临床参数速记，"
                       "内置间隔重复排程，进度本地保存。",
                  body=body, scripts=["js/cards.js"])


def stats_page(g: Graph) -> str:
    body = """
<div class="page pt3">
  <h1>数据统计</h1>
  <p class="small dim mt1 mb3" style="max-width:46em">图谱的结构画像：实体与关系如何分布、
    知识密度集中在哪些章节、哪些概念是骨架、证据覆盖率有多高。</p>
  <div class="grid auto" id="stWrap"><div class="empty">正在载入统计数据…</div></div>
</div>
"""
    return layout(depth=1, title="数据统计", active="stats/", canonical="stats/",
                  desc="口腔修复学知识图谱的结构统计：实体类型分布、关系谓词分布、章节知识密度、"
                       "枢纽概念、证据覆盖率与连通性分析。",
                  body=body, scripts=["js/stats.js"])


def about_page(g: Graph) -> str:
    m = g.meta
    type_rows = "".join(
        f'<tr><td><span class="chip-t" style="background:var(--t-{t})">{esc(g.TZH.get(t, t))}</span></td>'
        f'<td><code>{esc(t)}</code></td><td class="small dim">{esc(g.TDESC.get(t, ""))}</td>'
        f'<td class="nowrap">{collections.Counter(r[2] for r in g.N)[i]:,}</td></tr>'
        for i, t in enumerate(g.T))
    rel_counts = collections.Counter(e[2] for e in g.Ed)
    rel_rows = "".join(
        f'<tr><td>{esc(g.RZH.get(r, r))}</td><td><code>{esc(r)}</code></td>'
        f'<td class="small dim">{esc(g.RDESC.get(r, ""))}</td><td class="nowrap">{rel_counts[i]:,}</td></tr>'
        for i, r in enumerate(g.R))
    quality = {
        "aliased": sum(1 for r in g.N if r[4]),
        "defined": sum(1 for r in g.N if r[3]),
        "isolated": sum(1 for i in range(len(g.N)) if g.deg[i] == 0),
    }

    body = f"""
<div class="page pt3 prose">
  <h1>关于本项目</h1>
  <p class="lede" style="font-size:16px;color:var(--ink-2)">Ya-KG 是《口腔修复学》（第 8 版）的结构化知识图谱与配套检索站点。
    目标很朴素：让一本 400 页的教材，可以被<b>检索</b>、被<b>串联</b>、被<b>自测</b>，
    并且每一条结论都能回到原书的具体页码。</p>

  <h2 id="source">数据来源</h2>
  <table><tbody>
    <tr><td style="width:26%">教材</td><td>《口腔修复学》第 8 版</td></tr>
    <tr><td>主编 / 出版</td><td>{esc(m['src'])}</td></tr>
    <tr><td>覆盖范围</td><td>{esc(m['pages'])}（PDF 页码，含全部 10 章）</td></tr>
    <tr><td>抽取模型</td><td><code>{esc(m['model'])}</code></td></tr>
    <tr><td>规模</td><td>{m['n']:,} 实体 · {m['e']:,} 关系 · {m['f']:,} 知识点 · {m['p']:,} 定量参数 · {m['g']:,} 中英术语</td></tr>
  </tbody></table>

  <h2 id="method">构建方法</h2>
  <ol>
    <li><b>分章切分与版面还原</b>——按章节与自然段切分原文，修复扫描识别中常见的口腔专业错字
      （<code>𬌗</code> / <code>颞</code> / <code>髁突</code> / <code>龈</code> / <code>嵴</code> 等），保留页码锚点。</li>
    <li><b>实体与关系抽取</b>——在受控词表下抽取实体（14 类）与三元组（28 种谓词），
      每条关系尽量携带一句<b>原文依据句</b>。</li>
    <li><b>知识点结构化</b>——把「适应证 / 禁忌证 / 步骤 / 优缺点 / 并发症 / 注意事项」等段落
      拆成可独立检索的条目，共 {m['f']:,} 条，逐条标注页码。</li>
    <li><b>定量参数深度抽取轮次</b>——单独一轮只找带数值的临床标准，
      拆成「参数名 / 数值 / 单位 / 适用条件」四元组，得到 {m['p']:,} 项。</li>
    <li><b>归一与去重</b>——同义词合并到规范名（{quality['aliased']:,} 个实体带同义词），
      实体名在全库唯一，可作自然键。</li>
  </ol>

  <h2 id="quality">质量与局限</h2>
  <div class="grid c2" style="gap:14px;margin:16px 0">
    <div class="card pad"><h4>可以依赖的</h4><ul class="small">
      <li>{m['ext']:,} / {m['e']:,} 条关系（{m['ext'] / m['e'] * 100:.1f}%）带原文依据句，可逐句核对</li>
      <li>{quality['defined']:,} / {m['n']:,} 个实体有定义或释义</li>
      <li>实体名全库唯一，无重名歧义</li>
      <li>所有知识点与参数都标注了出处页码</li>
    </ul></div>
    <div class="card pad"><h4>需要留意的</h4><ul class="small">
      <li>{m['inf']:,} 条关系（{m['inf'] / m['e'] * 100:.1f}%）由<b>同段落共现推断</b>得出，界面上标注为「推断」，可能存在误连</li>
      <li>{quality['isolated']} 个实体为孤立节点，多为章节标题类占位概念</li>
      <li>页码为源 PDF 页码，与纸质书页码可能存在偏移</li>
      <li>抽取由模型完成，存在遗漏、断句错误与个别术语归类偏差</li>
      <li>本站不含教材原文段落、图表与影像，仅保留事实性知识点的结构化重述</li>
    </ul></div>
  </div>
  <blockquote>本站是<b>学习检索工具</b>，不是临床指南，也不能替代教材。
    任何临床决策请以最新教材、指南与执业规范为准。</blockquote>

  <h2 id="types">14 类实体</h2>
  <div class="table-wrap"><table><thead><tr><th>类型</th><th>标识符</th><th>说明</th><th>数量</th></tr></thead>
    <tbody>{type_rows}</tbody></table></div>

  <h2 id="relations">28 种关系谓词</h2>
  <div class="table-wrap"><table><thead><tr><th>谓词</th><th>标识符</th><th>说明</th><th>数量</th></tr></thead>
    <tbody>{rel_rows}</tbody></table></div>

  <h2 id="schema">数据格式</h2>
  <p><code>data/kg.json</code> 采用<b>列式数组编码</b>而非对象数组，把体积压到 1.8 MB（gzip 后约 400 KB）。
    每行是定长数组，字段顺序固定：</p>
  <pre><code>N: [ name, en, t, def, aliases[], chapters[], pages[], mentions ]
E: [ subject, object, predicate, evidence, inferred ]
F: [ entity, attribute, value, page ]
P: [ entity, param, value, unit, condition, page ]</code></pre>
  <p><code>t</code> 与 <code>predicate</code> 是指向 <code>T</code> / <code>R</code> 词表的下标；
    实体 ID 即该行在 <code>N</code> 中的下标。完整说明见仓库中的
    <a href="https://github.com/{REPO}/blob/main/data/SCHEMA.md" rel="noopener">data/SCHEMA.md</a>。</p>
  <p><b>提示：</b>实体 ID 是数组下标，跨版本不保证稳定；需要长期引用请使用 <code>name</code>（全库唯一）。</p>

  <h3>读取示例</h3>
  <pre><code>import json, urllib.request
kg = json.load(urllib.request.urlopen("{SITE_URL}/data/kg.json"))
T, R, N, E = kg["T"], kg["R"], kg["N"], kg["E"]

i = next(k for k, r in enumerate(N) if r[0] == "全冠")
for s, o, p, ev, inf in E:
    if s == i:
        print(f"全冠 --{{R[p]}}--&gt; {{N[o][0]}}", "（推断）" if inf else f"｜{{ev}}")</code></pre>
  <p>另有 CSV、JSON-Lines、Neo4j Cypher 与 RDF/Turtle 导出，见<a href="../downloads/">下载页</a>。</p>

  <h2 id="build">本地运行与二次开发</h2>
  <pre><code>git clone https://github.com/{REPO}.git
cd {REPO.split('/')[-1]}
python3 scripts/build.py --base /          # 生成 dist/
python3 -m http.server -d dist 8000        # 打开 http://localhost:8000</code></pre>
  <p>构建脚本只依赖 Python 3 标准库，无需 npm 或任何第三方包。
    站点为纯静态文件，可托管在 GitHub Pages、Netlify、Cloudflare Pages 或任意静态服务器。
    修改 <code>data/vocab.json</code> 可调整界面上的中文标签，无需改动图谱数据。</p>

  <h2 id="cite">如何引用</h2>
  <div class="card pad" style="margin:14px 0">
    <p class="mono small" style="color:var(--ink-2);line-height:1.8">Ya-KG: 口腔修复学（第8版）知识图谱.
      {time.strftime('%Y')}. {SITE_URL}/ ——
      数据源自《口腔修复学》第 8 版，赵铱民主编，人民卫生出版社。</p>
    <button class="btn sm mt2" data-copy="Ya-KG: 口腔修复学（第8版）知识图谱. {time.strftime('%Y')}. {SITE_URL}/ —— 数据源自《口腔修复学》第8版，赵铱民主编，人民卫生出版社。" data-copy-label="引用信息已复制">复制引用</button>
  </div>
  <p>引用具体概念时，每个词条页面右侧的「复制引用信息」按钮会附上页码与稳定链接。</p>

  <h2 id="license">许可与免责</h2>
  <ul>
    <li><b>代码</b>（构建脚本、样式与前端）：MIT License。</li>
    <li><b>派生数据</b>（结构化知识点与关系）：CC BY-NC-SA 4.0，仅限非商业的学习与研究用途。</li>
    <li><b>教材原文</b>版权归原作者与人民卫生出版社所有。本项目不提供原文、图表与影像，
      仅提取事实性知识点用于学习检索，属于对事实的重新组织。</li>
    <li>本项目为非官方学习工具，与出版社及原作者无隶属关系；若权利人认为存在不当使用，
      请通过 <a href="https://github.com/{REPO}/issues" rel="noopener">GitHub Issues</a> 联系，我们会及时处理。</li>
  </ul>

  <h2 id="contrib">发现错误？</h2>
  <p>知识图谱一定有错。若你发现术语归类不当、关系连错、参数抄错或页码偏移，
    欢迎提 <a href="https://github.com/{REPO}/issues" rel="noopener">Issue</a>
    或直接改 <code>data/kg.json</code> 提 PR——附上页码与原文一句话即可，我们会尽快核对。</p>
</div>
"""
    return layout(depth=1, title="关于", active="about/", canonical="about/",
                  desc="Ya-KG 的数据来源、抽取方法、质量与局限、数据格式说明、引用方式与开源许可。",
                  body=body)


def downloads_page(g: Graph, files: list[tuple[str, str, str, int]]) -> str:
    rows = "".join(
        f'<tr><td><a href="../{path}" download>{esc(path.split("/")[-1])}</a></td>'
        f'<td class="small dim">{esc(desc)}</td><td class="tiny dimmer nowrap">{esc(fmt)}</td>'
        f'<td class="tiny dimmer nowrap">{size / 1024:.0f} KB</td></tr>'
        for path, desc, fmt, size in files)
    body = f"""
<div class="page pt3 prose" style="max-width:900px">
  <h1>数据下载</h1>
  <p class="lede small dim">完整图谱与全部派生导出。所有文件均为 UTF-8 编码，
    CSV 带 BOM 以便 Excel 直接打开。数据以 CC BY-NC-SA 4.0 发布。</p>
  <div class="table-wrap mt3"><table>
    <thead><tr><th style="width:32%">文件</th><th>内容</th><th>格式</th><th>大小</th></tr></thead>
    <tbody>{rows}</tbody></table></div>

  <h2>导入示例</h2>
  <h3>Neo4j</h3>
  <pre><code># 将 kg-neo4j.cypher 放入 Neo4j 的 import 目录后
cat kg-neo4j.cypher | cypher-shell -u neo4j -p &lt;password&gt;</code></pre>
  <h3>Python / pandas</h3>
  <pre><code>import pandas as pd
ent = pd.read_csv("{SITE_URL}/downloads/kg-entities.csv")
rel = pd.read_csv("{SITE_URL}/downloads/kg-relations.csv")
rel.merge(ent, left_on="subject", right_on="name").head()</code></pre>
  <h3>Anki</h3>
  <p><code>kg-anki.csv</code> 为「正面 / 背面 / 标签」三列，可在 Anki 中直接以逗号分隔导入，
    标签为实体类型与章节号。</p>
  <h3>RDF / SPARQL</h3>
  <pre><code>from rdflib import Graph
g = Graph().parse("kg.ttl", format="turtle")
print(len(g), "triples")</code></pre>
  <p class="small dim mt3">格式说明见<a href="../about/#schema">关于页的数据格式一节</a>，
    或仓库中的 <a href="https://github.com/{REPO}/blob/main/data/SCHEMA.md" rel="noopener">data/SCHEMA.md</a>。</p>
</div>
"""
    return layout(depth=1, title="数据下载", canonical="downloads/",
                  desc="下载口腔修复学知识图谱的完整数据：JSON、CSV、JSON-Lines、Neo4j Cypher、"
                       "RDF/Turtle 与 Anki 卡片导出。",
                  body=body)


def notfound_page(g: Graph) -> str:
    body = """
<div class="page" style="padding:12vh 0 14vh;text-align:center">
  <div style="font-size:64px;font-weight:700;letter-spacing:-.04em;color:var(--ink-4);line-height:1">404</div>
  <h1 class="mt2">这个页面不在图谱里</h1>
  <p class="dim mt1">链接可能已经失效，或者概念编号有误。</p>
  <div class="row mt3" style="justify-content:center">
    <button class="btn primary" data-palette>搜索概念</button>
    <a class="btn" href="/">返回首页</a>
    <a class="btn" href="/explorer/">图谱浏览器</a>
  </div>
</div>
"""
    return layout(depth=0, title="页面未找到", desc="页面未找到", body=body)


# ════════════════════════════════════════════════════════════ data files ══
def write_json(path: Path, obj) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    txt = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    path.write_text(txt, "utf-8")
    return len(txt.encode("utf-8"))


def build_data(g: Graph, out: Path):
    T, TZH = g.T, g.TZH

    # full graph (adds readable label maps for the explorer)
    full = {
        "meta": g.meta, "T": T, "R": g.R, "CH": g.CH,
        "TZH": TZH, "RZH": g.RZH,
        "N": g.N, "E": g.Ed, "F": g.F, "P": g.P,
    }
    write_json(out / "data" / "kg.json", full)

    # lightweight search index
    write_json(out / "data" / "search.json", {
        "T": T, "TZH": TZH,
        "I": [[r[0], r[1], r[2], "|".join(r[4]), r[7], g.deg[i], r[5]]
              for i, r in enumerate(g.N)],
    })

    # glossary
    write_json(out / "data" / "glossary.json", {
        "T": T, "TZH": TZH, "CH": g.CH,
        "G": [[i, r[0], r[1], r[2], r[5], r[6][:6]] for i, r in enumerate(g.N) if r[1]],
    })

    # parameters
    units = collections.Counter(p[3] for p in g.P)
    write_json(out / "data" / "parameters.json", {
        "T": T, "TZH": TZH, "CH": g.CH,
        "units": units.most_common(),
        "P": [[p[0], g.name(p[0]), g.N[p[0]][2], p[1], p[2], p[3], p[4], p[5], g.N[p[0]][5]] for p in g.P],
    })

    # study cards, sharded by chapter
    for ch in map(int, g.CH):
        cards = []
        for i in g.chapter_nodes(ch):
            n = g.N[i]
            facts = [[g.F[k][1] or "要点", g.F[k][2]] for k in g.fct[i][:8]]
            params = [[g.P[k][1], g.P[k][2] + g.P[k][3], g.P[k][4]] for k in g.prm[i][:8]]
            if not (n[3] or facts or params):
                continue
            cards.append([i, n[0], n[1], n[2], n[3], facts, params])
        write_json(out / "data" / "cards" / f"ch{ch}.json", {"T": T, "TZH": TZH, "C": cards})

    # statistics
    tcount = collections.Counter(r[2] for r in g.N)
    rcount = collections.Counter(e[2] for e in g.Ed)
    fcount = collections.Counter()
    pcount = collections.Counter()
    for f in g.F:
        for c in g.N[f[0]][5]:
            fcount[c] += 1
    for p in g.P:
        for c in g.N[p[0]][5]:
            pcount[c] += 1
    comps = g.components()
    pages = {p for r in g.N for p in r[6]}
    hubs = sorted(range(len(g.N)), key=lambda i: -g.deg[i])[:18]
    ptop = sorted((i for i in range(len(g.N)) if g.prm[i]), key=lambda i: -len(g.prm[i]))[:16]

    write_json(out / "data" / "stats.json", {
        "meta": g.meta, "T": T, "TZH": TZH, "RZH": g.RZH,
        "types": [[T[i], tcount[i]] for i, _ in tcount.most_common()],
        "rels": [[g.R[i], rcount[i]] for i, _ in rcount.most_common()],
        "chapters": [[f"第{k}章", len(g.chapter_nodes(int(k)))] for k in g.CH],
        "chapterFacts": [[f"第{k}章", fcount[int(k)]] for k in g.CH],
        "hubs": [[g.name(i), g.deg[i], i] for i in hubs],
        "paramTop": [[g.name(i), len(g.prm[i]), i] for i in ptop],
        "attrs": collections.Counter(f[1] or "要点" for f in g.F).most_common(20),
        "units": units.most_common(14),
        "quality": {"aliased": sum(1 for r in g.N if r[4]),
                    "defined": sum(1 for r in g.N if r[3])},
        "graph": {"maxDeg": max(g.deg), "isolated": sum(1 for d in g.deg if d == 0),
                  "lcc": max(comps.values()), "components": len(comps), "pages": len(pages)},
    })


# ═══════════════════════════════════════════════════════════════ exports ══
def csv_bytes(header, rows) -> bytes:
    buf = io.StringIO(newline="")
    w = csv.writer(buf, lineterminator="\r\n")
    w.writerow(header)
    w.writerows(rows)
    return "\ufeff".encode("utf-8") + buf.getvalue().encode("utf-8")


TTL_ESC = str.maketrans({"\\": "\\\\", '"': '\\"', "\n": "\\n", "\r": "\\r", "\t": "\\t"})


def build_exports(g: Graph, out: Path) -> list[tuple[str, str, str, int]]:
    d = out / "downloads"
    d.mkdir(parents=True, exist_ok=True)
    files: list[tuple[str, str, str, int]] = []

    def emit(name: str, payload: bytes, desc: str, fmt: str):
        (d / name).write_bytes(payload)
        files.append((f"downloads/{name}", desc, fmt, len(payload)))

    emit("kg-entities.csv", csv_bytes(
        ["id", "name", "en", "type", "type_zh", "definition", "aliases", "chapters", "pages", "mentions", "degree"],
        [[i, r[0], r[1], g.T[r[2]], g.TZH.get(g.T[r[2]], ""), r[3], " | ".join(r[4]),
          " ".join(map(str, r[5])), " ".join(map(str, r[6])), r[7], g.deg[i]]
         for i, r in enumerate(g.N)]),
        f"{len(g.N):,} 个实体：名称、英文、类型、定义、同义词、章节、页码、提及次数、连接度", "CSV")

    emit("kg-relations.csv", csv_bytes(
        ["subject", "predicate", "object", "predicate_zh", "evidence", "inferred", "subject_id", "object_id"],
        [[g.name(s), g.R[p], g.name(o), g.RZH.get(g.R[p], ""), ev, int(bool(inf)), s, o]
         for s, o, p, ev, inf in g.Ed]),
        f"{len(g.Ed):,} 条关系三元组，含原文依据句与「是否推断」标记", "CSV")

    emit("kg-facts.csv", csv_bytes(
        ["entity", "entity_id", "attribute", "value", "page"],
        [[g.name(f[0]), f[0], f[1], f[2], f[3]] for f in g.F]),
        f"{len(g.F):,} 条结构化知识点：适应证 / 步骤 / 优缺点 / 并发症等，逐条带页码", "CSV")

    emit("kg-parameters.csv", csv_bytes(
        ["entity", "entity_id", "type_zh", "parameter", "value", "unit", "condition", "page"],
        [[g.name(p[0]), p[0], g.tzh(p[0]), p[1], p[2], p[3], p[4], p[5]] for p in g.P]),
        f"{len(g.P):,} 项定量临床参数：参数名、数值、单位、适用条件、页码", "CSV")

    emit("kg-glossary.csv", csv_bytes(
        ["zh", "en", "type_zh", "aliases", "chapters", "pages", "url"],
        [[r[0], r[1], g.TZH.get(g.T[r[2]], ""), " | ".join(r[4]),
          " ".join(map(str, r[5])), " ".join(map(str, r[6])), f"{SITE_URL}/c/{i}/"]
         for i, r in enumerate(g.N) if r[1]]),
        f"{g.meta['g']:,} 条中英术语对照，含同义词与稳定链接", "CSV")

    anki = []
    for i, r in enumerate(g.N):
        tags = f"口腔修复学 {g.TZH.get(g.T[r[2]], g.T[r[2]])} " + " ".join(f"第{c}章" for c in r[5])
        back = []
        if r[3]:
            back.append(r[3])
        if r[1]:
            back.append(f"<i>{r[1]}</i>")
        for k in g.fct[i][:6]:
            back.append(f"<b>{g.F[k][1]}</b>：{g.F[k][2]}")
        for k in g.prm[i][:6]:
            back.append(f"<b>{g.P[k][1]}</b>：{g.P[k][2]}{g.P[k][3]}")
        if not back:
            continue
        anki.append([r[0], "<br>".join(back), tags])
    emit("kg-anki.csv", csv_bytes(["front", "back", "tags"], anki),
         f"{len(anki):,} 张 Anki 卡片（正面 / 背面 / 标签），可直接以逗号分隔导入", "CSV")

    jl = io.StringIO()
    for i, r in enumerate(g.N):
        jl.write(json.dumps({
            "id": i, "name": r[0], "en": r[1], "type": g.T[r[2]], "definition": r[3],
            "aliases": r[4], "chapters": r[5], "pages": r[6], "mentions": r[7],
            "url": f"{SITE_URL}/c/{i}/",
            "facts": [{"attribute": g.F[k][1], "value": g.F[k][2], "page": g.F[k][3]} for k in g.fct[i]],
            "parameters": [{"name": g.P[k][1], "value": g.P[k][2], "unit": g.P[k][3],
                            "condition": g.P[k][4], "page": g.P[k][5]} for k in g.prm[i]],
            "relations_out": [{"predicate": g.R[g.Ed[k][2]], "object": g.name(g.Ed[k][1]),
                               "evidence": g.Ed[k][3], "inferred": bool(g.Ed[k][4])} for k in g.out[i]],
            "relations_in": [{"predicate": g.R[g.Ed[k][2]], "subject": g.name(g.Ed[k][0]),
                              "evidence": g.Ed[k][3], "inferred": bool(g.Ed[k][4])} for k in g.inn[i]],
        }, ensure_ascii=False) + "\n")
    emit("kg.jsonl", jl.getvalue().encode("utf-8"),
         "JSON-Lines：每行一个实体，附带全部知识点、参数与双向关系，适合流式处理与 LLM 检索", "JSONL")

    cy = io.StringIO()
    cy.write("// Ya-KG · 口腔修复学知识图谱 → Neo4j\n")
    cy.write("// cat kg-neo4j.cypher | cypher-shell -u neo4j -p <password>\n\n")
    cy.write("CREATE CONSTRAINT kg_concept_name IF NOT EXISTS "
             "FOR (c:Concept) REQUIRE c.name IS UNIQUE;\n\n")

    def cyq(s):
        return "'" + str(s).replace("\\", "\\\\").replace("'", "\\'").replace("\n", " ") + "'"

    cy.write(":begin\n")
    for i, r in enumerate(g.N):
        cy.write(f"CREATE (:Concept:{g.T[r[2]]} {{id:{i}, name:{cyq(r[0])}, en:{cyq(r[1])}, "
                 f"definition:{cyq(r[3])}, chapters:{r[5]}, pages:{r[6]}, mentions:{r[7]}}});\n")
    cy.write(":commit\n:begin\n")
    for s, o, p, ev, inf in g.Ed:
        cy.write(f"MATCH (a:Concept {{id:{s}}}),(b:Concept {{id:{o}}}) "
                 f"CREATE (a)-[:{g.R[p].upper()} {{evidence:{cyq(ev)}, inferred:{str(bool(inf)).lower()}}}]->(b);\n")
    cy.write(":commit\n")
    emit("kg-neo4j.cypher", cy.getvalue().encode("utf-8"),
         "Neo4j 导入脚本：实体带类型标签，关系带原文依据句与推断标记", "Cypher")

    ns = f"{SITE_URL}/vocab#"
    ent = f"{SITE_URL}/c/"
    tt = io.StringIO()
    tt.write(f"""@prefix rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix dct:  <http://purl.org/dc/terms/> .
@prefix kg:   <{ns}> .
@prefix c:    <{ent}> .

kg:ConceptScheme a skos:ConceptScheme ;
  dct:title "口腔修复学知识图谱 (Ya-KG)"@zh ;
  dct:source "口腔修复学 第8版, 赵铱民主编, 人民卫生出版社" .

""")
    for t in g.T:
        tt.write(f'kg:{t} a rdfs:Class ; rdfs:label "{g.TZH.get(t, t).translate(TTL_ESC)}"@zh, '
                 f'"{g.TEN.get(t, t).translate(TTL_ESC)}"@en .\n')
    tt.write("\n")
    for r in g.R:
        tt.write(f'kg:{r} a rdf:Property ; rdfs:label "{g.RZH.get(r, r).translate(TTL_ESC)}"@zh, '
                 f'"{r.replace("_", " ")}"@en .\n')
    tt.write("\n")
    for i, r in enumerate(g.N):
        tt.write(f"c:{i} a skos:Concept, kg:{g.T[r[2]]} ;\n")
        tt.write(f'  skos:prefLabel "{r[0].translate(TTL_ESC)}"@zh ;\n')
        if r[1]:
            tt.write(f'  skos:prefLabel "{r[1].translate(TTL_ESC)}"@en ;\n')
        for a in r[4]:
            tt.write(f'  skos:altLabel "{a.translate(TTL_ESC)}"@zh ;\n')
        if r[3]:
            tt.write(f'  skos:definition "{r[3].translate(TTL_ESC)}"@zh ;\n')
        tt.write("  skos:inScheme kg:ConceptScheme .\n")
    tt.write("\n")
    for s, o, p, ev, inf in g.Ed:
        tt.write(f"c:{s} kg:{g.R[p]} c:{o} .\n")
    emit("kg.ttl", tt.getvalue().encode("utf-8"),
         "RDF/Turtle：SKOS 概念方案 + 自定义谓词，可载入任意三元组库做 SPARQL 查询", "Turtle")

    kgjson = (out / "data" / "kg.json")
    files.insert(0, ("data/kg.json", "完整知识图谱（列式编码，站点与全部导出的唯一数据源）",
                     "JSON", kgjson.stat().st_size))
    return files


# ══════════════════════════════════════════════════════════════ site meta ══
def build_sitemaps(g: Graph, out: Path):
    today = time.strftime("%Y-%m-%d")

    def urlset(entries):
        rows = "".join(
            f"<url><loc>{SITE_URL}/{loc}</loc><lastmod>{today}</lastmod>"
            f"<changefreq>{cf}</changefreq><priority>{pr}</priority></url>"
            for loc, cf, pr in entries)
        return ('<?xml version="1.0" encoding="UTF-8"?>\n'
                '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                + rows + "</urlset>\n")

    pages = [("", "weekly", "1.0")]
    pages += [(h, "weekly", "0.9") for h, _, _ in NAV[1:]]
    pages += [("downloads/", "monthly", "0.6")]
    pages += [(f"chapters/{k}/", "monthly", "0.8") for k in g.CH]
    (out / "sitemap-pages.xml").write_text(urlset(pages), "utf-8")

    concepts = [(f"c/{i}/", "monthly", "0.7" if g.deg[i] > 6 else "0.5") for i in range(len(g.N))]
    (out / "sitemap-concepts.xml").write_text(urlset(concepts), "utf-8")

    (out / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        f"<sitemap><loc>{SITE_URL}/sitemap-pages.xml</loc><lastmod>{today}</lastmod></sitemap>"
        f"<sitemap><loc>{SITE_URL}/sitemap-concepts.xml</loc><lastmod>{today}</lastmod></sitemap>"
        "</sitemapindex>\n", "utf-8")

    (out / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\n\nSitemap: {SITE_URL}/sitemap.xml\n", "utf-8")


def build_pwa(out: Path, base: str, version: str):
    (out / "manifest.webmanifest").write_text(json.dumps({
        "name": "Ya-KG · 口腔修复学知识图谱",
        "short_name": "Ya-KG",
        "description": "《口腔修复学》第8版结构化知识图谱：概念检索、关系浏览、参数速查与记忆卡片。",
        "start_url": "./",
        "scope": "./",
        "display": "standalone",
        "background_color": "#f7f8f8",
        "theme_color": "#0d6e7a",
        "lang": "zh-Hans",
        "categories": ["education", "medical", "reference"],
        "icons": [
            {"src": "./assets/img/icon-192.png", "sizes": "192x192", "type": "image/png"},
            {"src": "./assets/img/icon-512.png", "sizes": "512x512", "type": "image/png"},
            {"src": "./assets/img/icon-512.png", "sizes": "512x512", "type": "image/png",
             "purpose": "maskable"},
            {"src": "./assets/img/favicon.svg", "sizes": "any", "type": "image/svg+xml"},
        ],
        "shortcuts": [
            {"name": "图谱浏览器", "url": "./explorer/"},
            {"name": "临床参数", "url": "./parameters/"},
            {"name": "记忆卡片", "url": "./cards/"},
        ],
    }, ensure_ascii=False, indent=2), "utf-8")

    (out / "sw.js").write_text(f"""/* Ya-KG service worker · build {version} */
const V = 'ya-kg-{version}';
const B = new URL('./', self.registration.scope).pathname;   // base path, whatever we are mounted at
const CORE = [B, B + 'explorer/', B + 'assets/css/app.css', B + 'assets/js/core.js', B + 'data/search.json'];

self.addEventListener('install', e => {{
  self.skipWaiting();
  e.waitUntil(caches.open(V).then(c => c.addAll(CORE).catch(() => {{}})));
}});
self.addEventListener('activate', e => {{
  e.waitUntil(caches.keys()
    .then(ks => Promise.all(ks.filter(k => k !== V).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
}});
self.addEventListener('fetch', e => {{
  const r = e.request;
  if (r.method !== 'GET') return;
  const u = new URL(r.url);
  if (u.origin !== location.origin) return;

  // versioned assets + data: cache-first
  if (/\\/(assets|data)\\//.test(u.pathname)) {{
    e.respondWith(caches.match(r).then(hit => hit || fetch(r).then(res => {{
      if (res.ok) {{ const cp = res.clone(); caches.open(V).then(c => c.put(r, cp)); }}
      return res;
    }})));
    return;
  }}
  // documents: network-first, fall back to cache then offline shell
  if (r.mode === 'navigate' || (r.headers.get('accept') || '').includes('text/html')) {{
    e.respondWith(fetch(r).then(res => {{
      const cp = res.clone(); caches.open(V).then(c => c.put(r, cp));
      return res;
    }}).catch(() => caches.match(r).then(hit => hit || caches.match(B))));
  }}
}});
""", "utf-8")


# ═════════════════════════════════════════════════════════════════ main ══
def copy_assets(out: Path):
    dst = out / "assets"
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(SITE / "assets", dst)
    for p in sorted(dst.rglob("*")):
        if p.is_file():
            ASSET_V[str(p.relative_to(dst)).replace(os.sep, "/")] = digest(p)


def main():
    global SITE_URL
    ap = argparse.ArgumentParser(description="Build the Ya-KG static site.")
    ap.add_argument("--out", default="dist", help="output directory (default: dist)")
    ap.add_argument("--base", default="/", help="URL base path, e.g. /Ya-KG/ (used for PWA scope)")
    ap.add_argument("--site-url", default=None, help="absolute site URL for canonical links & sitemap")
    ap.add_argument("--skip-concepts", action="store_true", help="skip the 4882 concept pages (fast preview)")
    args = ap.parse_args()

    if args.site_url:
        SITE_URL = args.site_url.rstrip("/")
    # configure-pages emits "/" for user sites and "/repo" for project sites —
    # normalise either into exactly one leading and trailing slash
    base = "/" + args.base.strip("/") + "/" if args.base.strip("/") else "/"

    t0 = time.time()
    out = (ROOT / args.out).resolve()
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    kg, vocab = load()
    g = Graph(kg, vocab)
    copy_assets(out)

    version = hashlib.sha256(
        (DATA / "kg.json").read_bytes() + b"|" + "|".join(sorted(ASSET_V.values())).encode()
    ).hexdigest()[:10]

    def write(rel: str, htmltext: str):
        p = out / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(htmltext, "utf-8")

    print("· data files")
    build_data(g, out)
    print("· exports")
    files = build_exports(g, out)

    print("· pages")
    write("index.html", landing(g))
    write("explorer/index.html", explorer_page(g))
    write("glossary/index.html", glossary_page(g))
    write("parameters/index.html", parameters_page(g))
    write("cards/index.html", cards_page(g))
    write("stats/index.html", stats_page(g))
    write("about/index.html", about_page(g))
    write("downloads/index.html", downloads_page(g, files))
    write("chapters/index.html", chapters_index(g))
    write("404.html", notfound_page(g))
    for ch in map(int, g.CH):
        write(f"chapters/{ch}/index.html", chapter_page(g, ch))

    if not args.skip_concepts:
        print(f"· {len(g.N):,} concept pages", end="", flush=True)
        for i in range(len(g.N)):
            write(f"c/{i}/index.html", concept_page(g, i))
            if i % 1000 == 0:
                print(".", end="", flush=True)
        print()

    print("· sitemap / pwa")
    build_sitemaps(g, out)
    build_pwa(out, base, version)
    (out / ".nojekyll").write_text("", "utf-8")

    total = sum(p.stat().st_size for p in out.rglob("*") if p.is_file())
    count = sum(1 for p in out.rglob("*") if p.is_file())
    print(f"\n✓ built {count:,} files · {total / 1024 / 1024:.1f} MB · "
          f"{time.time() - t0:.1f}s → {out.relative_to(ROOT) if out.is_relative_to(ROOT) else out}")
    print(f"  base={base}  site_url={SITE_URL}  version={version}")


if __name__ == "__main__":
    main()
