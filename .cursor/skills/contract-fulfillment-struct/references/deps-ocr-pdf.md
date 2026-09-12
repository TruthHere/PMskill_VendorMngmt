# 环境依赖：OCR vs pdf-read vs 全局 PDF 伴侣

## 当前策略（MVP）

| 场景 | 做法 |
|------|------|
| 文本型 PDF | `pdf-read` → 本地 pypdf/pdfplumber |
| 扫描件 / 复杂版式 | `pdf-read` → **SoMark**（`SOMARK_API_KEY`） |
| SoMark 不可用 | 优先页识图 + PM 手填（**不装**本机 OCR） |
| 从正文抽付款节点 | **Skill 1** `extract_contract_pdf.py`（吃 pdf-read 的 JSON） |

**OCR 本机安装（tesseract 等）：当前阶段不做。** 扫描件优先 SoMark；见 `.cursor/skills/pdf-read/`。

Agent：**不要**主动 `brew install` tesseract / poppler 除非用户明确要求。

---

## 三者区别

| | **OCR（本机）** | **pdf-read（项目 Skill）** | **PDF 伴侣（全局 Skill）** |
|--|-----------------|---------------------------|---------------------------|
| 是什么 | 扫描件认字软件 | 分类 → 读出正文 | Anthropic 通用 PDF 操作（合并/拆分/填表） |
| 本项目 | 暂缓 | **读报价单/合同 PDF 主入口** | **不装在本仓库**；仅用户明确要改 PDF 文件时用全局那份 |
| 步骤 4a | 不用 | **必用（只读正文）** | 非入口；禁止用来读文字 |

---

## SoMark 配置

见 `.cursor/skills/pdf-read/references/somark-setup.md`（Skill 内 `.somark.secret` 或 `~/.pmskills/somark.secret`）。

```bash
pip install somark
echo 'sk-your-api-key' > .cursor/skills/pdf-read/.somark.secret
chmod 600 .cursor/skills/pdf-read/.somark.secret
```

---

## 全局 PDF 伴侣 —— 本仓库不安装

路径（若本机已装）：`~/.cursor/skills/pdf/`  
本项目 **不要** 再放一份在 `.agents/skills/pdf/` 或 `.cursor/skills/`。  
读报价单/合同正文以 **`pdf-read`** 为准。

---

## Agent 步骤 4a（当前）

1. 跑 `pdf-read/scripts/read_pdf.py`（只要正文）
2. 跑 Skill 1 `extract_contract_pdf.py --read-json …` → `payment_nodes` 候选
3. 失败 → 最多渲优先页识读；禁止全本翻页；不足则 PM 手填
4. 不安装 OCR
