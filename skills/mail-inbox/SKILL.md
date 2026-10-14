---
name: mail-inbox
description: >-
  辅助 Skill：待处理邮件入口。用户把整封 .eml，或 Outlook 另存的 .msg，放进项目根「待处理邮件」并说
  「处理待处理邮件」时，扫描、分类、交给履约/请款/变更。办成的归档进采购包并拿走原件。
  不建已处理邮件，不连邮箱。看不准和回信留给对话问人。务必在提到待处理邮件、
  处理邮件、邮件分类、mail-inbox、把邮件分给履约/变更/请款时使用。
---

# 邮件入口（mail-inbox · 辅助 Skill）

**这版给人用的入口**是项目根目录的 `待处理邮件/`。用户自己把整封邮件放进去，再说「处理待处理邮件」。标准邮件是 `.eml`。从 Outlook 另存的 `.msg` 也收：先转成标准邮件，再走同一条分类。转好的那封才归档。不要教用户连邮箱，不要跑 IMAP / 企微轮询。

**全局原则**：先理解再处理（见 `skill-orchestration`）——分类看主题+正文；低置信不要改台账。`Re:` / 引用原文的回信：先读**最新一段**，按 `intent-taxonomy.md`「线程回信怎么判」覆写后再交业务 Skill。

## 编排硬规则（摘要）

跨 Skill / 进度 / 合同 PDF / 邮件分发 → 先读 `<skills-root>/skill-orchestration/ALWAYS.md`（细节见同目录 `README.md`）。
单独使用功能 Skill 时禁止擅自串联履约/请款；脚本已串完的不要双跑；时间线对人只有 `项目档案/00_进度计划/关键节点时间线.html` 一份。
`skills-root` = 本机 Skills 安装根（WorkBuddy 常见 `~/.workbuddy/skills/`）。命令写成 `python3 <skills-root>/<技能名>/scripts/…`。

## 定位

读 `待处理邮件/` → 分类 → 交给业务 Skill。

| 做 | 不做 |
|----|------|
| 扫描项目根 `待处理邮件/` 里的 `.eml` 和 `.msg` | 改采购包 Tracker、Change Log、请款账（交给业务 Skill） |
| 能确定的：分类并分发；归档成功后拿走待处理里的原件 | 建「已处理邮件」文件夹 |
| 回信、看不准、像新建项目的：留下，在对话里问 | 从这夹里跑建项；连邮箱、IMAP、企微轮询 |

## 权威文档

| 文件 | 内容 |
|------|------|
| `references/intent-taxonomy.md` | 意图优先级、防误伤、enrichment |
| `references/io-contract.md` | 输入输出 JSON、路由字段 |
| `references/agent-mail.md` | 企微 agent-mail → `.eml` 入口 |
| `skill-orchestration`（Rule/说明书，非 Skill） | 系统内谁先谁后（唯一编排真源） |

## 脚本入口

用户说「处理待处理邮件」并指出项目后，只跑这一条：

```bash
python3 <skills-root>/mail-inbox/scripts/process_drop_folder.py \
  --project-root "/path/to/project"
```

然后用脚本打印的清单回答用户。每条看 `status`：

| status | 你怎么说 |
|--------|----------|
| `done` | 办成了什么，归档在哪 |
| `skipped_duplicate` | 这封已经在某个归档夹，没有再办 |
| `archived_needs_you` | 文件已归档，但这件事还要用户拍板（把 `note` 说出来） |
| `needs_you` | 原件还在待处理里。回信要先读最新一段，看不准就问用户。确认后再用下面的 `dispatch_mail`，然后**再跑一次**本脚本，让它把已归档的原件拿走 |
| `left` | 说明为什么没动。不是 `.eml` / `.msg` 的点名。`.msg` 读不了的也点名。像新建项目的，告诉用户回到对话里建 |

单封补处理（只在你已经读过、并改对意图之后）：

```bash
python3 <skills-root>/mail-inbox/scripts/dispatch_mail.py \
  --project-root "/path/to/project" \
  --eml "/path/to/待处理邮件/msg.eml"
```

排障只看分类：`dispatch_mail.py --classify-only --eml "…"`。`.msg` 也可以直接给这条。

## 调用链

```text
待处理邮件/*.eml 或 *.msg
  → .msg 先转成同夹里的 .eml
  → process_drop_folder.py
       ├─ 能确定的 fulfillment / 请款 / 变更 → 现有业务 Skill 归档
       ├─ 回信、看不准 → 留下，对话里问
       └─ 像新建项目 → 留下，不建项
```

## 评测

```bash
python3 <skills-root>/mail-inbox/scripts/run_all_evals.py
```
