---
name: mail-inbox
description: >-
  辅助 Skill：项目邮箱前台。IMAP / 企微 agent-mail JSON / 粘贴 /.eml 收取、解析、意图分类与路由
  （履约/变更/请款相关/初始化/未知）；不改 Tracker、Change Log、请款 ledger。
  被 WorkBuddy 定时任务与业务 Skill 0/1/2/3 调用。务必在提到专用邮箱、IMAP、企微邮箱、
  agent-mail、收信分类、邮件路由、inbox、mail-inbox、把邮件分给履约/变更时使用。
disable-model-invocation: true
---

# 邮件入口（mail-inbox · 辅助 Skill）

**全局原则**：先理解再处理（见 `skill-orchestration`）——分类看主题+正文+问卷答案语境，禁止 FAQ 模板句误伤业务意图；低置信进 pending。

## 定位

项目邮箱**邮局前台**：收信 → 分类 → 交给业务 Skill。**不**办履约 / 变更 / 请款业务。

| 做 | 不做 |
|----|------|
| 拉取 `.eml` / 吃 agent-mail JSON，落盘 `inbox/` | 改采购包 Tracker |
| 解析主题、正文、附件清单 | 写 Change Log / 请款 ledger |
| 意图分类 + 路由（`intent-taxonomy.md`） | 渲染卡片、算关键节点 |
| 低置信 → `pending` | 替业务 Skill 跑完整 handler；不调企微 MCP |

## 权威文档

| 文件 | 内容 |
|------|------|
| `references/intent-taxonomy.md` | 意图优先级、防误伤、enrichment |
| `references/io-contract.md` | 输入输出 JSON、路由字段 |
| `references/agent-mail.md` | 企微 agent-mail → `.eml` 入口 |
| `skill-orchestration` | 系统内谁先谁后（唯一编排真源） |

## 脚本入口

分类 / 分发（`.eml` 已落盘时）：

```bash
python3 .cursor/skills/mail-inbox/scripts/dispatch_mail.py \
  --project-root "/path/to/project" \
  --eml "/path/to/msg.eml"
```

**企微 agent-mail**（Agent 用 MCP 拉信写成 JSON 后，跑这一条）：

```bash
python3 .cursor/skills/mail-inbox/scripts/ingest_agent_mail.py \
  --project-root "/path/to/project"
# 或：--message-json "/path/to/msg.json"
```

**IMAP 163**（本机/旧路）：

```bash
python3 .cursor/skills/mail-inbox/scripts/poll_mailbox.py --project-root "/path/to/project"
python3 .cursor/skills/mail-inbox/scripts/run_mailbox_worker.py --once
```

排障只看分类：`dispatch_mail.py --classify-only --eml "…"`。

## 调用链

```text
IMAP  或  企微 agent-mail JSON  或  .eml
  → mail-inbox（收 + 分）
       ├─ project_init      → Skill 0
       ├─ fulfillment.*     → Skill 1
       ├─ payment_claim.*   → Skill 2（按五步推进；客户批复才占用）
       ├─ change.*          → Skill 3
       └─ unknown           → pending
```

## 评测

```bash
python3 .cursor/skills/mail-inbox/scripts/run_all_evals.py
```
