# doc-parser-bench

[English](README.md) | **简体中文**

横向评测各家文档解析器的表格识别质量。打分依据是你自己标的标准答案，
不是别人的公开榜单。

第一版故意做小：统一一套解析器接口，只算单元格级 P/R/F1，输出一份能一眼
看出错在哪的 HTML 报告。

![status](https://img.shields.io/badge/python-3.10%2B-blue)
![license](https://img.shields.io/badge/license-MIT-green)

## 这个工具解决什么问题

挑文档解析器（RAGFlow、MinerU、Unstructured……）的时候，基本只有两条路：

- 看公开榜单。但 PubTabNet 那类样本是学术论文，不是你手上真正要处理的文档；
- 把两个结果摆一起用眼睛看。主观、复现不了，也没法跟人交代。

这个工具补的就是这块：

- 拿**你自己的文档**跑多个解析器；
- 出**可量化、可复现**的 P/R/F1；
- 生成**左右对照**的 HTML 报告，哪一格错了直接标出来。

## 功能

- 解析器抽象层，加一个后端只写一个类
- 单元格级 precision / recall / F1，微平均
- 漏检的表格按 0 分算——什么都不输出的解析器拿不到高分
- 自带 6 个合成样本，PDF 和标准答案一一对应
- 每个文档出一份 HTML 报告，逐单元格标出差异
- 带单元测试：`python tests/test_metrics.py`
- ⚠️ 短板：单元格级指标看不出**结构**错误（行列顺序错、合并单元格错），
  详见[后续计划](#后续计划)

## 目录结构

```
doc-parser-bench/
├── parsers/
│   ├── base.py               # 抽象接口 + Table / TableCell
│   ├── pdfplumber_parser.py  # 规则型基线，默认启用
│   └── ragflow.py            # 可选深度学习解析器，需自建服务
├── metrics/table.py          # 单元格级 P/R/F1
├── templates/report.html     # Jinja2 + Bootstrap 报告模板
├── samples/                  # 6 个合成 PDF + *_gt.json 标准答案
│   └── annotation_guide.md   # 标注规则
├── scripts/generate_samples.py   # 重新生成自带样本
├── tests/test_metrics.py
├── benchmark.py              # 核心：跑解析器、打分、组装渲染数据
├── ground_truth.py           # 读 *_gt.json -> Table 对象
├── report.py                 # 命令：单文档 -> 单份报告
└── run_all.py                # 命令：全部样本 -> 报告 + 汇总
```

## 安装

需要 Python 3.10 以上（开发用的是 3.13）。

```bash
git clone https://github.com/rei0-t/doc-parser-bench.git
cd doc-parser-bench

python -m venv venv
source venv/Scripts/activate      # Windows
# source venv/bin/activate        # Linux / macOS

pip install -r requirements.txt
```

> pip 装得慢就换镜像，国内一般一条命令解决：
> `pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple`

## 用法

### 跑单个文档

```bash
python report.py --input samples/sample_001.pdf --output reports/sample_001.html
```

标准答案默认按 `samples/sample_001_gt.json` 找，想换别的用 `--ground-truth` 指定。

### 跑全部样本

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

浏览器打开 `reports/sample_003.html`：

- 每个解析器一行评分
- 标准答案和解析结果左右对照
- 绿 = 对，红 = 多识别，黄 = 漏识别
- 解析器完全没找到的表格，会单独提示

### 跑测试

```bash
python tests/test_metrics.py
```

### 重新生成自带样本

```bash
python scripts/generate_samples.py
```

## 设计取舍

### 为什么要加一层抽象

各家的接口和输出格式差得挺远：

| 解析器 | 类型 | 输出 |
|---|---|---|
| `pdfplumber` | 进程内的库 | `list[list[str]]` |
| `ragflow` | REST 服务 | 带 `<table>` 的 HTML |

`parsers/base.py` 只定一条规矩：`parse_tables() -> List[Table]`。评测代码不用
关心表格是谁产出的。加后端只写一个类，别的地方一行不动。

### 为什么第一版不用 TEDS

TEDS 是表格评测的金标准，但有两个现实问题：

- 得先把 HTML 解析成树，再实现树编辑距离算法。这本身就是个独立项目；
- 要用的 `apted` 库装起来很折腾。

所以第一版先只算单元格级：

```
precision = 正确单元格数 / 解析器输出的单元格数
recall    = 正确单元格数 / 标准答案的单元格数
f1        = 2 * precision * recall / (precision + recall)
```

**短板说实话**：它看不见结构错误。`sample_003` 就是现成例子——标准答案里
Warranty 横跨两列，pdfplumber 输出成普通单元格，文字一样、位置一样，指标照样
判对；换成 TEDS 就会因为丢了 span 扣分。这块后面必须补。

### 为什么漏检的表格要算 0 分，而不是跳过

如果解析器一张表都没找到，你却把这些标准答案悄悄从统计里删掉，它的分数反而
比「找到了大部分」的解析器还高。所以没有对应预测的表格一律按完全漏检算
（P=0、R=0）；反过来，多识别出来的表格只报出来，不扣分。

### 为什么要归一化文本

`metrics/table.py:normalize_cell_key()` 在比较前会转小写、合并多余空白。OCR 和
各家的输出在行尾空格、大小写上本来就不一致，这层是去噪，不是放宽对内容的要求。

## 样本

6 个合成文档，都由 `scripts/generate_samples.py` 从同一份描述同时生成 PDF 和
标准答案。这样标注和文档不可能对不上。

| 文件 | 场景 | 难点 |
|---|---|---|
| `sample_001.pdf` | 发票 | 普通带框线表格 |
| `sample_002.pdf` | 年报 | 一页两个表格 |
| `sample_003.pdf` | 产品规格 | 合并单元格（`colspan`） |
| `sample_004.pdf` | 区域销售 | 横跨三列的分区标题 |
| `sample_005.pdf` | 产品清单 | 普通带框线表格 |
| `sample_006.pdf` | 统计年鉴 | **无框线**表格，一条表格线都没有 |

标注规则见 [`samples/annotation_guide.md`](samples/annotation_guide.md)。

> 想换真实公开文档（国标、年报、统计年鉴），把 PDF 换掉，用同一套 JSON 结构
> 重新标就行。**公司内部文档绝对不能用。**

## 实测结果

6 个样本、100 个标准答案单元格，`python run_all.py` 跑出来：

| 解析器 | Precision | Recall | F1 | 说明 |
|---|---|---|---|---|
| `pdfplumber` | 1.000 | 0.800 | 0.889 | 规则型基线，对无框线表格完全失明 |
| `ragflow` | n/a | n/a | n/a | 可选，需本地跑 RAGFlow 服务 |

分样本看：

| 样本 | Precision | Recall | F1 | 标准答案单元格 | 实际情况 |
|---|---|---|---|---|---|
| sample_001 | 1.000 | 1.000 | 1.000 | 18 | 18/18 全对 |
| sample_002 | 1.000 | 1.000 | 1.000 | 24 | 24/24 全对 |
| sample_003 | 1.000 | 1.000 | 1.000 | 9 | 9/9 全对，但 span 结构仍丢了 |
| sample_004 | 1.000 | 1.000 | 1.000 | 17 | 17/17 全对 |
| sample_005 | 1.000 | 1.000 | 1.000 | 12 | 12/12 全对 |
| sample_006 | 0.000 | 0.000 | 0.000 | 20 | 表格根本没被检测到 |

重点看 `sample_006`。pdfplumber 靠表格线找表，无框线的表格对它等于不存在。
这不是 benchmark 的 bug——规则型基线就是这么失效的，也正好说明 ML 解析器的钱
花在哪。自己复现一遍：

```bash
python report.py --input samples/sample_006.pdf --output reports/sample_006.html
```

## 后续计划

- [ ] **TEDS 指标**：树编辑距离，做结构感知评测
- [ ] **接更多解析器**：MinerU、Unstructured
- [ ] **改进表格匹配**：按页码 + 包围盒对齐，而不是按顺序硬配
- [ ] **阅读顺序指标**：检测多栏布局的错序
- [ ] **OCR 评测**：字符级准确率，不只比单元格文本
- [ ] **换真实文档**：用国标 / 年报替换合成样本，沿用同一套标注结构
- [ ] **扩样本量**：覆盖 20 种以上文档类型

## 贡献

个人学习项目。issue 和 PR 都欢迎，但不保证及时回。

## 许可证

MIT，见 [LICENSE](LICENSE)。

## 致谢

- [pdfplumber](https://github.com/jsvine/pdfplumber)：规则型基线
- [RAGFlow](https://github.com/infiniflow/ragflow)：开源文档解析服务
- [PubTabNet](https://github.com/ibm-aur-nlp/PubTabNet)：表格评测方法的灵感来源
