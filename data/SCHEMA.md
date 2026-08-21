# 数据格式说明 · Data Schema

`data/kg.json` 是本项目的**唯一权威数据源**（single source of truth）。
网站、导出文件（CSV / Cypher / Turtle / JSON-Lines）全部由它构建生成。

文件采用**列式数组编码**（columnar array encoding）而非对象数组，以把体积压到 1.8 MB
（gzip 后约 400 KB）。每一行是一个定长数组，字段顺序固定。

```jsonc
{
  "meta": { … },   // 数据集元信息
  "T":    [ … ],   // 实体类型词表 (14)
  "R":    [ … ],   // 关系谓词词表 (28)
  "CH":   { … },   // 章节号 → 章节名 (10)
  "N":    [ … ],   // 实体 Nodes      (4882)
  "E":    [ … ],   // 关系 Edges      (9242)
  "F":    [ … ],   // 知识点 Facts    (5458)
  "P":    [ … ]    // 定量参数 Params (1368)
}
```

## `meta`

| 键 | 含义 |
|---|---|
| `title` | 数据集标题 |
| `src` | 来源教材 |
| `model` | 抽取所用模型 |
| `pages` | 覆盖的 PDF 页码范围 |
| `n` `e` `f` `p` | 实体 / 关系 / 知识点 / 参数 数量 |
| `g` | 具备英文译名的实体数（术语表条目数） |
| `ext` | 有原文依据句支撑的关系数 |
| `inf` | 由同段落共现**推断**的关系数 |

## `N` — 实体 Node

固定 8 个字段：

```jsonc
[ name, en, t, def, al, ch, pg, mt ]
//  0     1  2   3    4   5   6   7
```

| # | 字段 | 类型 | 含义 |
|---|---|---|---|
| 0 | `name` | string | 中文规范名，**全库唯一**，可作自然键 |
| 1 | `en` | string | 英文译名，无则空串 |
| 2 | `t` | int | 类型下标，指向 `T[t]` |
| 3 | `def` | string | 定义 / 释义 |
| 4 | `al` | string[] | 同义词与别名 |
| 5 | `ch` | int[] | 出现章节号，对应 `CH` 的键 |
| 6 | `pg` | int[] | 出现页码（PDF 页码） |
| 7 | `mt` | int | 全文提及次数，用于重要度排序 |

**实体 ID = 该行在 `N` 中的下标**（0-based）。`E` / `F` / `P` 均以此下标引用实体。

> ⚠️ ID 是数组下标，**跨版本不保证稳定**。需要长期稳定引用时请使用 `name`（全库唯一）。

## `E` — 关系 Edge

```jsonc
[ s, o, p, ev, inf ]
//  0  1  2   3   4
```

| # | 字段 | 类型 | 含义 |
|---|---|---|---|
| 0 | `s` | int | 主语实体 ID |
| 1 | `o` | int | 宾语实体 ID |
| 2 | `p` | int | 谓词下标，指向 `R[p]` |
| 3 | `ev` | string | 原文依据句（evidence），无则空串 |
| 4 | `inf` | 0\|1 | `1` = 由同段落共现**推断**得出，无直接依据句 |

三元组读作 `N[s] --R[p]--> N[o]`。

## `F` — 知识点 Fact

```jsonc
[ e, a, v, pg ]
//  0  1  2   3
```

| # | 字段 | 类型 | 含义 |
|---|---|---|---|
| 0 | `e` | int | 所属实体 ID |
| 1 | `a` | string | 属性名，如 `适应证` `步骤` `优点` `注意事项` |
| 2 | `v` | string | 属性值（一条知识点文本） |
| 3 | `pg` | int | 出处页码 |

共 40+ 种属性名，出现最多的为 `特点`(1057) `步骤`(540) `要求`(502) `适应证`(382) `分类`(361)。

## `P` — 定量参数 Param

```jsonc
[ e, n, v, u, c, pg ]
//  0  1  2  3  4   5
```

| # | 字段 | 类型 | 含义 |
|---|---|---|---|
| 0 | `e` | int | 所属实体 ID |
| 1 | `n` | string | 参数名，如 `肩台宽度` `聚合度` |
| 2 | `v` | string | 数值或区间，如 `0.8~1.0` `2°~5°` |
| 3 | `u` | string | 单位，如 `mm` `°` `%` `MPa` |
| 4 | `c` | string | 适用条件 / 语境 |
| 5 | `pg` | int | 出处页码 |

## `vocab.json`

`data/vocab.json` 为 `T`（类型）与 `R`（谓词）提供中英文可读标签与释义，
网站界面上的中文标签来源于此。修改后重新构建即可生效，不影响 `kg.json`。

## 读取示例

```python
import json
kg = json.load(open("data/kg.json", encoding="utf-8"))
T, R, N, E = kg["T"], kg["R"], kg["N"], kg["E"]

# 找出「全冠」的所有出向关系
i = next(k for k, r in enumerate(N) if r[0] == "全冠")
for s, o, p, ev, inf in E:
    if s == i:
        print(f"全冠 --{R[p]}--> {N[o][0]}", "（推断）" if inf else f"｜{ev}")
```

```javascript
const kg = await (await fetch("data/kg.json")).json();
const nodes = kg.N.map(([name, en, t, def, al, ch, pg, mt], i) =>
  ({ i, name, en, type: kg.T[t], def, aliases: al, chapters: ch, pages: pg, mentions: mt }));
```

## 数据质量说明

- 实体名全库唯一，无重名；4819/4882 具备英文译名；2023 个实体带同义词。
- 9242 条关系中 7656 条带原文依据句，1586 条（17.2%）为同段落共现推断，界面上标注为「推断」。
- 75 个实体为孤立节点（无关系连接），多为章节标题类占位概念。
- 页码为**源 PDF 页码**（p12–p391），与纸质书页码可能存在偏移。
- 术语已修复扫描识别错字（𬌗 / 颞 / 髁突 / 龈 / 嵴 等）。
