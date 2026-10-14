---
description: PM Skills 编排硬规则（项目级 · 始终生效）。跨 Skill 协作、进度/合同 PDF/邮件分发前必读。
alwaysApply: true
enabled: true
---

# PM Skills 编排（短规则）

> **这不是业务 Skill。** 不跑脚本、不收邮件、不出表。只规定「谁先谁后」。  
> **长文细节**：与本文件同级的 `README.md`（安装后位于 `<skills-root>/skill-orchestration/README.md`）。

## 如何找 `skills-root`

本机 Skills **安装根目录**（各技能文件夹的上一级）：

- WorkBuddy / CodeBuddy 常见：`~/.workbuddy/skills/`（或项目下 `.workbuddy/skills/` / `.codebuddy/skills/`）
- Cursor 本仓库开发时：`.cursor/skills/`；公共库在 `.cursor/lib/`（安装到 Agent 后与 Skill **并列**，仍按 `<skills-root>/project-foundation` 等查找）

命令一律写成：`python3 <skills-root>/<技能名>/scripts/….py …`  
**禁止**在说明书里写死某一家产品的家目录路径（例如不要写死 `.cursor/skills/...` 当唯一命令）。

## 硬规则

1. **涉及 2 个及以上 Skill**、进度计划链路、合同 PDF 管线、邮件分发、建包后同步、请款/变更与履约交叉 → 必须先读编排长文 `README.md`，再执行。
2. **单独使用**（用户只要转 MPP / 析关键节点 / 读 PDF，未提建包·请款·变更·Tracker）→ 只跑对应功能 Skill，**禁止**自动串联履约卡片或请款。
3. **系统内协作** → 服从长文的表 A（脚本）/ 表 B（Agent）；**禁止双跑**。建包后 sync 只重渲时间线，不算已补包级节点。
4. 功能 Skill（`mpp-to-excel`、`critical-nodes`、`read-pdf`）正文只描述自身能力；**系统挂钩以编排长文为准**，不要在功能 Skill 里发明新的兄弟调用顺序。
5. **读 PDF 正文** → **只用** `read-pdf`。通用 pdf 伴侣只在用户明确要合并/拆分/旋转/填表/加水印时才用。
6. **关键节点时间线对人只有一份**：`项目档案/00_进度计划/关键节点时间线.html`。禁止再往采购包文件夹写同名 HTML。
7. **建包后**：脚本只重渲上面那一份 HTML；同一回合 Agent 必须给**新包** merge 关键节点（不准整盘覆盖总包）。不准说「脚本会自动补包级节点」。
8. **业务回合禁止拆 Skill 脚本翻实现、禁止为修小毛病当场改 Skill。** 发现 bug 记下来另开任务。入口以各 `SKILL.md` 写明的命令为准。
9. **先理解再处理**：先搞清来件/附件在办哪一步、关键数字在哪，再落库；抽不出就 `pending`，禁止装懂。
10. **这版不连邮箱。** 建项只在对话里问完必填再跑 `init_project`（必填含币种和是否含税；不问邮箱）。后续邮件由人另存成整封 `.eml` 或 Outlook 的 `.msg`，放进该项目根目录 `待处理邮件/`。用户说「处理待处理邮件」后，先读 `mail-inbox`，只跑 `process_drop_folder.py`。`.msg` 先转成 `.eml` 再分类。办成的归档进采购包对应文件夹，并拿走待处理里的原件。不建「已处理邮件」。看不准、回信、像建项的邮件留在待处理里问人。

## 本规则挂载位置

| 环境 | 位置 |
|------|------|
| Cursor（本仓库） | `.cursor/rules/skill-orchestration.mdc`（由本文件对齐） |
| WorkBuddy / CodeBuddy **项目** | 建项时写入 `{项目根}/.codebuddy/rules/pm-skill-orchestration/RULE.mdc` |

**不要**写入用户全局 `~/.codebuddy/rules/`（避免串到无关对话）。改规则后请**新开对话**再测。
