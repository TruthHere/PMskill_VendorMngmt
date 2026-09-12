---
name: pdf-read
description: >-
  读 PDF 正文（报价单、合同、扫描件、图纸文字）→ 统一 JSON/Markdown。
  先判断文字版还是扫描件，再走本地抽字或 SoMark。
  用户说「帮我看这份 PDF」「读一下这个 PDF」「报价单 PDF」「合同 PDF」
  「扫描件 OCR / 认字」时务必使用本 Skill；不要用全局通用 pdf 伴侣来读文字。
  只读内容，不抽付款节点、不写 Tracker、不渲染履约卡片。
  可单独使用；系统内何时把正文交给履约 Skill 见 skill-orchestration。
---

# PDF 读取（pdf-read）

**全局原则**：先理解再处理（见 `skill-orchestration`）——先分类再选读法；读不清就标明局限，不编造正文。

## 定位

- **本 Skill**：只管「把 PDF 读成文字」→ 分类 → 选工具 → 统一输出
- **可单独使用**：交付 JSON/Markdown 即止；不写 Tracker、不渲染履约卡片、**不抽付款节点**
- **系统内协作**：合同/报价 PDF 先用本 Skill 读出正文，付款节点由 Skill 1 从正文抽取 → `.cursor/skills/skill-orchestration/SKILL.md`
- **不做**：合并、拆分、旋转、填表、加水印（那是全局 `pdf` 伴侣的事；本项目读文字不要去用它）

## 工作流

```
PDF 路径
  → classify_pdf.py          # 探测文本层、页数、大小、是否扫描件
  → read_pdf.py              # 按路由规则选工具
       ├─ 文本型 → 本地 pypdf/pdfplumber
       ├─ 扫描/复杂 → SoMark CLI
       └─ 页数 ≥30 或 扫描件 ≥20 页或 >30MB → SoMark --async --wait（防截断）
  → 统一 JSON（+ 可选把 markdown 交给用户）
```

路由细则见 [references/routing-rules.md](references/routing-rules.md)。

## 前置

```bash
pip install -r .cursor/skills/pdf-read/scripts/requirements.txt
pip install somark   # 或 npm install -g somark-js
```

**SoMark API Key（扫描件必配）** — 详见 [references/somark-setup.md](references/somark-setup.md)：

```bash
echo 'sk-your-api-key' > .cursor/skills/pdf-read/.somark.secret
chmod 600 .cursor/skills/pdf-read/.somark.secret
```

解析顺序：`SOMARK_API_KEY` 环境变量 → 项目根 `.somark.secret` → Skill 内 `.somark.secret` → `~/.pmskills/somark.secret`。

换平台时：**拷贝 Skill 目录并带上 `.somark.secret`**，或写 `~/.pmskills/somark.secret`。不依赖 Cursor MCP。

## 命令

### 1. 分类（可选单独跑）

```bash
python3 .cursor/skills/pdf-read/scripts/classify_pdf.py --pdf "/path/to/file.pdf"
```

### 2. 读取（主入口 · 报价单 / 合同 / 任意 PDF 都用这一条）

```bash
python3 .cursor/skills/pdf-read/scripts/read_pdf.py \
  --pdf "/path/to/file.pdf" \
  --out "/path/to/output.json"
```

## 输出字段（统一）

| 字段 | 说明 |
|------|------|
| `source` | `local` \| `somark` |
| `classification` | `text` \| `scan` \| `large` |
| `text` / `markdown` | 正文 |
| `page_count` | 页数 |
| `is_scan_likely` | 是否疑似扫描件 |
| `somark_async` | SoMark 是否用了 `--async --wait` |

**没有** `payment_nodes`。要从合同正文抽付款节点 → Skill 1 的 `extract_contract_pdf.py`（吃本 Skill 的 JSON）。

## SoMark 异步（防截断）

同步 `somark parse` 对长文档可能只返回部分 Markdown。`read_pdf.py` 在下列情况**自动**加 `--async --wait`：

| 条件 | 阈值 |
|------|------|
| 文件分类 `large` | > 30 MB |
| 任意 PDF | 页数 ≥ **30** |
| 扫描件 | 页数 ≥ **20** |

若输出 `text`/`markdown` 过短且正文引用「附件 B」但未见附件章节，应检查 `somark_async` 是否为 `true`；否则重跑或手动 async。

## 失败与回退

| 情况 | 动作 |
|------|------|
| SoMark 未配置 Key | 按 `references/somark-setup.md` 写入 `.somark.secret`；扫描件可回退「优先页识图 + 手填」 |
| SoMark 连接失败 | 同上 |
| 本地文本为空 | 自动尝试 SoMark（若 Key 已配） |
| 单文件 >200MB | 拒绝并提示拆分 |

## 如何被调用

需要读 PDF 时**先读取并遵循本 Skill**，示例：

```bash
python3 .cursor/skills/pdf-read/scripts/read_pdf.py \
  --pdf "<PDF路径>" \
  --out "<临时目录>/read.json"
```

用输出中的 `text` / `markdown` 继续后续步骤。**禁止**绕过本 Skill 直接全本渲图或自行装 OCR 当主路径。

系统内合同步骤 4a（读完正文再抽付款节点、确认、写卡片）见 `skill-orchestration`，不在本文件展开。
