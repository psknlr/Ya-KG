<div align="center">

# Ya-KG · 口腔修复学知识图谱

**把《口腔修复学》（第 8 版）读成一张可以走进去的知识网络**

[![Deploy](https://github.com/psknlr/Ya-KG/actions/workflows/pages.yml/badge.svg)](https://github.com/psknlr/Ya-KG/actions/workflows/pages.yml)
[![CI](https://github.com/psknlr/Ya-KG/actions/workflows/ci.yml/badge.svg)](https://github.com/psknlr/Ya-KG/actions/workflows/ci.yml)
[![Code: MIT](https://img.shields.io/badge/code-MIT-0d6e7a)](LICENSE)
[![Data: CC BY-NC-SA 4.0](https://img.shields.io/badge/data-CC%20BY--NC--SA%204.0-a8632a)](LICENSE)

### 🔗 **[psknlr.github.io/Ya-KG](https://psknlr.github.io/Ya-KG/)**

<img src="site/assets/img/og.png" width="820" alt="Ya-KG 预览">

</div>

---

## 这是什么

《口腔修复学》第 8 版全书（p12–p391）被拆解为一张结构化知识图谱，并配了一个**纯静态、零依赖**的检索站点。

| | |
|---|---|
| **4,882** | 实体概念，分 14 类（修复体 / 材料 / 临床操作 / 解剖结构 …），名称全库唯一 |
| **9,242** | 关系三元组，28 种谓词；其中 **7,656 条（82.8%）带原文依据句** |
| **5,458** | 结构化知识点（适应证 / 禁忌证 / 步骤 / 优缺点 / 并发症 …），逐条标注页码 |
| **1,368** | 定量临床参数，拆成「参数名 / 数值 / 单位 / 适用条件」四元组 |
| **4,819** | 中英术语对照 |

每一条结论都能回到原书的具体页码。

## 网站能做什么

| 页面 | 用途 |
|---|---|
| [**图谱浏览器**](https://psknlr.github.io/Ya-KG/explorer/) | 以任意概念为中心展开 1–3 跳邻域，力导向布局；按类型/章节筛选，导出子图 PNG |
| [**章节导读**](https://psknlr.github.io/Ya-KG/chapters/) | 对齐教材 10 章，按**章内中心度**排序核心概念，附本章参数表 |
| [**中英术语表**](https://psknlr.github.io/Ya-KG/glossary/) | 4,819 条对照，按首字母 / 类型 / 章节筛选，导出 CSV |
| [**临床参数速查**](https://psknlr.github.io/Ya-KG/parameters/) | 1,368 项带数值的标准，可排序可搜索——考前与椅旁最常查的一张表 |
| [**记忆卡片**](https://psknlr.github.io/Ya-KG/cards/) | 四种题型 + 间隔重复排程，进度存在本机 |
| [**数据统计**](https://psknlr.github.io/Ya-KG/stats/) | 实体/关系分布、章节密度、枢纽概念、证据覆盖率、连通性 |
| **4,882 个词条页** | 每个概念一个静态页面（`/c/<id>/`），可深链、可被搜索引擎索引、无 JS 也能读 |

还有：⌘K 全站检索、深浅色主题（跟随系统）、移动端适配、PWA 离线可用、打印样式。

## 数据，随手可取

```python
import json, urllib.request
kg = json.load(urllib.request.urlopen("https://psknlr.github.io/Ya-KG/data/kg.json"))
T, R, N, E = kg["T"], kg["R"], kg["N"], kg["E"]

i = next(k for k, r in enumerate(N) if r[0] == "全冠")
for s, o, p, ev, inf in E:
    if s == i:
        print(f"全冠 --{R[p]}--> {N[o][0]}", "（推断）" if inf else f"｜{ev}")
```

除 `kg.json` 外，[下载页](https://psknlr.github.io/Ya-KG/downloads/) 另提供由同一份数据生成的：

| 文件 | 说明 |
|---|---|
| `kg-entities.csv` · `kg-relations.csv` · `kg-facts.csv` · `kg-parameters.csv` · `kg-glossary.csv` | 分表 CSV（带 BOM，Excel 直接打开） |
| `kg.jsonl` | 每行一个实体，附全部知识点、参数与双向关系——适合流式处理与 RAG |
| `kg-neo4j.cypher` | Neo4j 导入脚本，实体带类型标签、关系带依据句 |
| `kg.ttl` | RDF/Turtle（SKOS 概念方案），可做 SPARQL 查询 |
| `kg-anki.csv` | Anki 卡片（正面 / 背面 / 标签） |

字段含义见 [`data/SCHEMA.md`](data/SCHEMA.md)。

## 仓库结构

```
data/
  kg.json          唯一权威数据源（列式编码，1.8 MB）
  vocab.json       类型与谓词的中英文标签 —— 改这里就能改界面用词
  SCHEMA.md        字段说明与读取示例
site/assets/       CSS / JS / 图标（手写，无框架、无构建工具）
scripts/
  build.py         静态站点生成器（仅用标准库）
  check.py         构建校验：数据完整性 + 全站链接 + 产物清单
legacy/            最初的单文件版 explorer（离线可用，保留作存档）
.github/workflows/ Pages 部署 + PR CI
```

## 本地运行

只需要 Python 3，**没有 npm、没有第三方包**：

```bash
git clone https://github.com/psknlr/Ya-KG.git
cd Ya-KG

python3 scripts/build.py --base /      # 生成 dist/（约 5 秒，4,946 个文件）
python3 scripts/check.py dist          # 校验：数据、产物、29 万条内部链接
python3 -m http.server -d dist 8000    # http://localhost:8000
```

开发时想跳过 4,882 个词条页以加快迭代：

```bash
python3 scripts/build.py --skip-concepts
```

常用参数：

| 参数 | 说明 |
|---|---|
| `--out DIR` | 输出目录，默认 `dist` |
| `--base /Ya-KG/` | 部署路径（只影响 PWA 作用域；页面链接全部是相对路径，任何路径都能跑） |
| `--site-url URL` | canonical 链接与 sitemap 用的绝对地址 |
| `--skip-concepts` | 跳过词条页，快速预览 |

## 部署

`main` 分支有改动时，[`pages.yml`](.github/workflows/pages.yml) 自动构建并发布到 GitHub Pages。
无需任何手动设置——工作流里 `configure-pages` 带 `enablement: true`，仓库没开 Pages 时会自动开启。

产物不入库——`dist/` 在 CI 中现场生成，所以仓库里永远只有源数据和源代码。

> **不要再加第二个 Pages 工作流。** GitHub 在 Settings → Pages 里推荐的 Jekyll 模板
> （`jekyll-gh-pages.yml`）会用 Jekyll 构建**仓库根目录**并发布，也就是把 README 当成网站，
> 而且和 `pages.yml` 共用 `pages` 并发组——两者会互相抢占，谁后跑谁覆盖。
> 本仓库只应有 `pages.yml` 一个部署工作流。

## 发现错误？

知识图谱一定有错。术语归类不当、关系连错、参数抄错、页码偏移——欢迎提
[Issue](https://github.com/psknlr/Ya-KG/issues) 或直接改 `data/kg.json` 提 PR，
附上页码与原文一句话即可。详见 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 已知局限

- **1,586 条关系（17.2%）由同段落共现推断**，没有直接原文依据句，界面上标注为「推断」，可能误连。
- 75 个实体是孤立节点，多为章节标题类占位概念。
- 页码是**源 PDF 页码**，与纸质书可能有偏移。
- 抽取由模型完成，存在遗漏、断句错误与个别术语归类偏差。
- 实体 ID 是数组下标，**跨版本不保证稳定**；需要长期引用请用 `name`（全库唯一）。

> **这是学习检索工具，不是临床指南，也不能替代教材。**
> 任何临床决策请以最新教材、指南与执业规范为准。

## 许可

- **代码**（`scripts/`、`site/`、`.github/`）：[MIT](LICENSE)
- **派生数据**（`data/`）：[CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/)，仅限非商业的学习与研究
- **教材原文**版权归原作者与人民卫生出版社所有。本项目不含原文、图表与影像，
  仅提取事实性知识点重新组织。为非官方学习工具，与出版社及原作者无隶属关系。

引用方式见 [CITATION.cff](CITATION.cff)。

---

<details>
<summary><b>English summary</b></summary>

**Ya-KG** turns *Prosthodontics* (口腔修复学, 8th ed., People's Medical Publishing House)
into a browsable knowledge graph plus a dependency-free static site.

- **4,882** entities across 14 types · **9,242** typed relations (82.8% carrying a
  verbatim evidence sentence) · **5,458** structured knowledge points ·
  **1,368** quantitative clinical parameters · **4,819** bilingual term pairs.
- Every fact is traceable to a source page.
- The site ships an interactive force-directed explorer, a bilingual glossary, a
  sortable clinical-parameter table, spaced-repetition flashcards, a statistics
  dashboard, and **4,882 pre-rendered concept pages** that work without JavaScript.
- Data is published as JSON, CSV, JSON-Lines, Neo4j Cypher, RDF/Turtle and Anki CSV.
- The generator is a single stdlib-only Python script — no npm, no frameworks.

```bash
python3 scripts/build.py --base /   # → dist/
python3 scripts/check.py dist       # data + link integrity
```

Code is MIT; the derived data is CC BY-NC-SA 4.0. The underlying textbook remains
copyright of its authors and publisher — no prose, figures or images are reproduced.
This is an unofficial study aid, not clinical guidance.

</details>
