# 参与改进

这张图谱由模型抽取而成，**一定有错**。最有价值的贡献就是订正它。

## 报告一个错误

开一个 [Issue](https://github.com/psknlr/Ya-KG/issues)，尽量带上：

1. **概念名**或词条链接（如 `https://psknlr.github.io/Ya-KG/c/1234/`）
2. **错在哪**——术语归类、关系连错、参数数值、页码偏移、错别字……
3. **教材原文一句话 + 页码**——这是最关键的一条，有它就能直接核对并修正

## 直接改数据

所有内容都来自 [`data/kg.json`](data/kg.json)，字段说明见 [`data/SCHEMA.md`](data/SCHEMA.md)。
文件是**每行一条记录**的紧凑 JSON，diff 很干净，可以直接改。

```bash
git checkout -b fix/shoulder-width
# 编辑 data/kg.json
python3 scripts/build.py --skip-concepts   # 快速构建
python3 scripts/check.py dist              # 必须通过
```

改动时请注意：

- **实体 ID 是数组下标。** 不要在 `N` 中间插入或删除行——那会让 `E` / `F` / `P` 里
  所有引用错位。新增实体请**追加到 `N` 末尾**。
- 实体名必须**全库唯一**，`check.py` 会验证。
- 关系的 `inferred` 标记：找到原文依据句就填进 `ev` 并把第 5 个字段改成 `0`。
- 改完记得同步 `meta` 里的计数（`check.py` 会核对）。

## 改界面用词

类型和谓词的中文标签在 [`data/vocab.json`](data/vocab.json)，改完重新构建即可，
不需要动图谱数据。

## 改站点

- 样式：[`site/assets/css/app.css`](site/assets/css/app.css) —— 手写 CSS，全部走设计令牌。
  深色主题的令牌块有两份（媒体查询 + 属性选择器），**改一份必须同步另一份**，文件里有注释标注。
- 交互：[`site/assets/js/`](site/assets/js/) —— 原生 ES5 风格，无框架无构建。
- 页面结构：[`scripts/build.py`](scripts/build.py) —— 每个页面一个函数，共用 `layout()`。

提 PR 前请跑：

```bash
python3 scripts/build.py --base / && python3 scripts/check.py dist
```

`check.py` 会校验数据完整性、产物清单、全部 JSON 以及约 29 万条站内链接。
CI 会跑同样的检查。

## 行为准则

就事论事，对人友善。这是给学生用的工具，把它做得更准确就是最好的贡献。
