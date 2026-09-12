# PDF 读取路由规则

## 分类标准（classify_pdf.py）

| 信号 | 判定 |
|------|------|
| 全页 native 字符数 < 80 | `scan`（疑似扫描件） |
| 文件大小 > 30 MB | `large` |
| 否则且有可读文本 | `text` |

## 路由表

| 分类 | 首选工具 | 命令 |
|------|----------|------|
| `text` | 本地 | `read_pdf.py` 内 pypdf → pdfplumber |
| `scan` | SoMark | `somark parse <pdf> --formats md --out <dir>` |
| `large` 或 **页数 ≥30** 或 **扫描件 ≥20 页** | SoMark **异步** | `somark parse … --async --wait --out <dir>` |
| `text` 但本地为空 | SoMark（回退，同上 async 规则） | 同上 |

## 限制（与 SoMark 文档对齐）

| 项 | 上限 |
|----|------|
| 单文件 | 200 MB |
| 账号 QPS | 1（等上一次完成再提交） |
| 免费额度 | 500 页/日，2000 页/月 |

## 不做的事

- 不默认安装 tesseract / poppler OCR 链
- 不全本渲图（调用方最多优先页识图）
- 不抽付款节点 / 合同金额（那是 Skill 1 的事）
- 不处理 PDF 合并/拆分/填表（全局 `pdf` 伴侣；本项目读文字不用它）
