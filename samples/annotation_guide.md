# Ground Truth 标注规则 / Annotation Rules

本文件定义 `*_gt.json` 的产生方式。**标注规则本身就是技术判断**：什么算
对、什么算错，必须写清楚，否则评测数字没有意义。

This file defines how the `*_gt.json` files are produced. The rules *are* part
of the evaluation: if "what counts as correct" is not written down, the numbers
mean nothing.

---

## 1. 基本原则 / Principles

1. 只标注**表格**，正文段落不标。
   Only tables are annotated. Running text is out of scope.
2. 每个表格一个 JSON 对象；一个文档一个 JSON 文件。
   One JSON object per table, one JSON file per document.
3. 只使用**公开数据**或**自己造的假数据**。
   Never use company-internal documents — legal and confidentiality risk.
4. 空白单元格不标注。空不是内容。
   Empty cells are not annotated. Emptiness is not content.

## 2. 坐标规则 / Coordinates

| 项目 | 规则 |
|---|---|
| 行号 `row` | 从 0 开始（第一行 = 0） |
| 列号 `col` | 从 0 开始（第一列 = 0） |
| 合并单元格 | 只在**左上角**记录，其余被覆盖的格子不重复标注 |
| 跨页表格 | 拆成两个 table（`page` 分别为 1、2），表头每页都要标 |

## 3. 文本规则 / Text

- 保留原始大小写（评测时统一 lowercase）。
- 去掉前后空格；多个连续空格合并成一个；换行符替换成空格。
- 数字按文档原样抄写，不做单位换算（`210 x 297 mm` 保持原样）。
- 表格内的图片标注为 `[图片]`。
- 截断或无法辨认的文本标注为 `[无法辨认]`。

评测阶段的归一化在 `metrics/table.py:normalize_cell_key()` 中完成，
标注阶段不要重复做归一化。

## 4. 合并单元格 / Spanned cells

- 横向合并用 `colspan`，纵向合并用 `rowspan`。
- 被合并覆盖的格子**不标注**（只标左上角）。
- 规则型解析器（pdfplumber）通常把合并单元格拆成多个格子，
  这会体现在评测分数上——这正是要测出来的东西。

## 5. JSON 格式 / Schema

```json
{
  "filename": "sample_001.pdf",
  "tables": [
    {
      "page": 1,
      "num_rows": 3,
      "num_cols": 3,
      "cells": [
        {"row": 0, "col": 0, "text": "销售额", "rowspan": 1, "colspan": 1},
        {"row": 0, "col": 1, "text": "数量",   "rowspan": 1, "colspan": 1},
        {"row": 2, "col": 0, "text": "合计",   "rowspan": 1, "colspan": 3}
      ]
    }
  ]
}
```

## 6. 标注前 Checklist

- [ ] 文件名对应正确（`sample_001.pdf` ↔ `sample_001_gt.json`）
- [ ] `num_rows` / `num_cols` 与实际表格一致
- [ ] 所有非空单元格都已标注
- [ ] 合并单元格的 `rowspan` / `colspan` 正确，且未重复标注被覆盖格子
- [ ] 文本无多余空格与换行
- [ ] 跨页表格已拆分
- [ ] JSON 格式校验通过：`python -m json.tool sample_001_gt.json`

## 7. 本仓库的样例 / Bundled samples

仓库自带的 6 个样例全部是**合成数据**，由 `scripts/generate_samples.py`
根据同一份描述同时生成 PDF 和 JSON，因此二者不可能不一致。
换成真实文档时，请按上面的规则重新标注。
