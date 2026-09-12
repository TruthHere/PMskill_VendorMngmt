# PDF 能力依赖（不内嵌上游原文）

上游 skill：[`anthropics/skills` → `pdf`](https://github.com/anthropics/skills/tree/main/skills/pdf)  
许可：Anthropic 专有条款（**禁止**将 SKILL.md 等材料复制、再分发或制作衍生副本到本仓库的 `bundled/`）。

因此本目录**不** vendoring 上游文件。履约 Skill 的封装方式是：

1. **读 PDF 正文**：项目 Skill **`pdf-read`**（`read_pdf.py`）
2. **抽付款节点**：本 Skill `scripts/extract_contract_pdf.py`（吃 pdf-read 的 JSON）
3. **流程强制**见 `.cursor/skills/skill-orchestration/references/pdf-pipeline.md` 与父级 `SKILL.md` 步骤 4a
4. **通用 PDF 操作**（合并/拆分/填表）若需要，用**本机全局** Skill：`~/.cursor/skills/pdf/`。  
   **本仓库不安装**，不要再 `npx skills add` 进项目。

读报价单 / 合同文字以 **`pdf-read`** 为准，不要用全局伴侣读文字。
