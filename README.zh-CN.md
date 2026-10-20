# doc-parser-bench

[English](README.md) | **简体中文**

一个用来横向评测**文档解析器**表格提取质量的开源工具，以人工标注的
ground truth 作为评分基准。

> 刻意做小的第一版：一个统一的解析器接口、单元格级 precision / recall / F1，
> 以及带单元格差异高亮的 HTML 对比报告。

![status](https://img.shields.io/badge/python-3.10%2B-blue)
![license](https://img.shields.io/badge/license-MIT-green)

## 为什么做这个工具

在选文档解析器（RAGFlow、MinerU、Unstructured……）的时候，大多数人只有两条路：

- 信公开的学术榜单（比如 PubTabNet），但那些样本是论文，不是你真正要解析的那类文档；
- 把两个输出摆在一起用眼睛比，主观、不可复现、也没法写进汇报。

这个工具让你可以：

- 在**自己的文档**上跑多个解析器；
- 拿到**可量化、可复现的指标**（precision / recall / F1）；
- 打开一份**左右并排的 HTML 报告**，错在哪一格一眼就能看到。

## 功能特性

- ✅ 解析器抽象层——新增一个后端只需要写一个类
- ✅ 单元格级 precision / recall / F1，采用微平均（micro-average）
- ✅ 漏掉的表格按 miss 计分（什么都不输出的解析器得 0 分，而不是满分）
- ✅ 内置 6 个合成样本，PDF 与 ground truth 一一对应
- ✅ 每个文档生成一份 HTML 报告，逐单元格高亮差异
- ✅ 单元测试（`python tests/test_metrics.py`）
- ⚠️ **当前局限：** 单元格级指标看不出**结构**错误（行列顺序错、合并单元格错）。
  详见[后续计划](#后续计划)。

## 项目结构

```
doc-parser-bench/
├── parsers/
│   ├── base.py               # 抽象接口 + Table / TableCell
│   ├── pdfplumber_parser.py  # 规则型基线（默认启用）
│   └── ragflow.py            # 可选深度学习解析器（需自建服务）
├── metrics/table.py          # 单元格级 P/R/F1
├── templates/report.html     # Jinja2 + Bootstrap 报告模板
├── samples/                  # 6 个合成 PDF + *_gt.json 标注
│   └── annotation_guide.md   # 标注规则
├── scripts/generate_samples.py   # 重新生成内置样本
├── tests/test_metrics.py
├── benchmark.py              # 核心：跑解析器、打分、构造渲染数据
├── ground_truth.py           # 加载 *_gt.json -> Table 对象
├── report.py                 # CLI：单文档 -> 单份 HTML 报告
└── run_all.py                # CLI：全部样本 -> 报告 + 汇总
```

## 安装

**环境要求：** Python 3.10+（开发时使用 3.13）。

```bash
git clone https://github.com/rei0-t/doc-parser-bench.git
cd doc-parser-bench

python -m venv venv
source venv/Scripts/activate      # Windows
# source venv/bin/activate        # Linux / macOS

pip install -r requirements.txt
```

> 如果 `pip install` 卡住或很慢，换国内镜像通常立刻见效：
> `pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple`

## 使用

### 评测单个文档

```bash
python report.py --input samples/sample_001.pdf --output reports/sample_001.html
```

ground truth 会自动按 `samples/sample_001_gt.json` 查找，
也可以用 `--ground-truth` 显式指定。

### 评测全部样本

```bash
python run_all.py
# -> reports/sample_00X.html  +  reports/summary.json
```

```
=== Summary over all samples ===
Parser         Precision    Recall        F1
pdfplumber         1.000     0.800     0.889
```

### 看报告

用浏览器打开 `reports/sample_003.html`，可以看到：

- 每个解析器一个 precision / recall / F1 评分；
- ground truth 与解析器输出左右并排；
- 绿色 = 正确，红色 = 多识别（false positive），黄色 = 漏识别（false negative）；
- 解析器完全没找到的表格会被单独标出来。

### 跑测试

```bash
python tests/test_metrics.py
```

### 重新生成内置样本

```bash
python scripts/generate_samples.py
```

## 架构

### 设计取舍

**为什么要做抽象层？**

各家解析器的 API 和输出格式差异很大：

| 解析器 | 类型 | 返回什么 |
|---|---|---|
| `pdfplumber` | 进程内库 | `list[list[str]]` |
| `ragflow` | REST 服务 | 带 `<table>` 的 HTML |

`parsers/base.py` 只约定一件事——`parse_tables() -> List[Table]`——所以评测代码
永远不需要知道表格是哪个后端产出的。新增一个后端只写一个类，其余代码一行不改。

**为什么用单元格级指标，而不是 TEDS？**

TEDS（Tree-Edit-Distance-based Similarity）是表格评测的黄金标准，但是：

- 它需要先把 HTML 解析成树，再实现树编辑距离算法，本身就是一个小项目；
- 依赖的 `apted` 库安装体验很差，文档也少。

第一版用单元格级指标：

```
precision = 正确单元格数 / 解析器输出的单元格数
recall    = 正确单元格数 / ground truth 的单元格数
f1        = 2 * precision * recall / (precision + recall)
```

**局限（说清楚，不藏）：** 单元格级指标看不见结构错误。`sample_003` 就是例子：
标注里 *Warranty* 横跨两列，pdfplumber 输出成普通单元格——文字一样、位置一样，
指标仍然判「正确」，而 TEDS 会给这个丢失的 span 扣分。后续版本必须迁到 TEDS。

**为什么漏掉的表格要计分，而不是跳过？**

如果一个解析器一张表都没找到，悄悄把这些 ground truth 表格从统计里剔除，
它反而会比「找到了大部分表格」的解析器分数更高。所以没有对应预测的 ground truth
表格一律按完全漏检计分（precision 0、recall 0）；而解析器多识别出来的表格只报告、
不扣分。

**为什么要归一化单元格文本？**

`metrics/table.py:normalize_cell_key()` 在比较前会转小写、合并多余空白。OCR 输出
和不同解析器在行尾空格、大小写上并不一致；归一化是去掉这类噪声，而不是放宽对
内容本身的比较。

## 样本

6 个**合成**文档，由 `scripts/generate_samples.py` 从同一份描述同时生成 PDF 和
ground truth——所以标注和文档不可能对不上。

| 文件 | 场景 | 难点 |
|---|---|---|
| `sample_001.pdf` | 发票 | 普通带框线表格 |
| `sample_002.pdf` | 年报 | 一页两个表格 |
| `sample_003.pdf` | 产品规格 | 合并单元格（`colspan`） |
| `sample_004.pdf` | 区域销售 | 横跨三列的分区标题 |
| `sample_005.pdf` | 产品清单 | 普通带框线表格 |
| `sample_006.pdf` | 统计年鉴 | **无框线**表格（没有任何表格线） |

标注规则见 [`samples/annotation_guide.md`](samples/annotation_guide.md)。

> 想换成**真实的公开文档**（国标、年报、统计年鉴），把 PDF 换掉、用同样的 JSON
> schema 重新标注即可。**绝对不要**用公司内部文档。

## 评测结果

在 6 个内置样本（共 100 个 ground truth 单元格）上，用 `python run_all.py` 实测：

| 解析器 | Precision | Recall | F1 | 说明 |
|---|---|---|---|---|
| `pdfplumber` | 1.000 | 0.800 | 0.889 | 规则型基线；对无框线表格完全失明 |
| `ragflow` | n/a | n/a | n/a | 可选；需要本地跑 RAGFlow 服务 |

分样本：

| 样本 | Precision | Recall | F1 | GT 单元格 | 观察到的现象 |
|---|---|---|---|---|---|
| sample_001 | 1.000 | 1.000 | 1.000 | 18 | 18/18 全对 |
| sample_002 | 1.000 | 1.000 | 1.000 | 24 | 24/24 全对 |
| sample_003 | 1.000 | 1.000 | 1.000 | 9 | 9/9 全对（但 span 结构仍丢失） |
| sample_004 | 1.000 | 1.000 | 1.000 | 17 | 17/17 全对 |
| sample_005 | 1.000 | 1.000 | 1.000 | 12 | 12/12 全对 |
| sample_006 | 0.000 | 0.000 | 0.000 | 20 | 表格完全没被检测到 |

最值得说的是 `sample_006`：pdfplumber 靠表格线找表，无框线表格对它等于不存在。
这不是 benchmark 的 bug，恰恰是规则型基线的真实失效场景，也正是 ML 解析器值那个
成本的原因。复现：

```bash
python report.py --input samples/sample_006.pdf --output reports/sample_006.html
```

## 后续计划

- [ ] **TEDS 指标**——用树编辑距离做结构感知评测
- [ ] **更多解析器**——MinerU、Unstructured
- [ ] **更好的表格匹配**——按页码 + 包围盒对齐预测表与 GT 表，而不是按顺序
- [ ] **阅读顺序指标**——检测多栏布局的阅读顺序错误
- [ ] **OCR 评测**——字符级准确率，而不只是单元格文本
- [ ] **真实公开文档**——用国标 / 年报替换合成样本，沿用同一套标注 schema
- [ ] **扩大样本集**——覆盖 20+ 种文档类型

## 参与贡献

这是个人学习项目。欢迎提 issue 和 PR，但响应可能不及时。

## 许可证

MIT，详见 [LICENSE](LICENSE)。

## 致谢

- [pdfplumber](https://github.com/jsvine/pdfplumber)——规则型基线
- [RAGFlow](https://github.com/infiniflow/ragflow)——开源文档解析服务
- [PubTabNet](https://github.com/ibm-aur-nlp/PubTabNet)——表格评测方法的灵感来源
