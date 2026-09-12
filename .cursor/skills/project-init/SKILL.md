---
name: project-init
description: >-
  业务 Skill 0 · 项目初始化。新建项目根、.skill/project.json、空 Tracker、项目背景、
  绑定专用邮箱；对话建项时可选归档进度计划并按 skill-orchestration 表 B 编排
  schedule-mpp-excel → schedule-critical-nodes。不建采购包、不做 RFP/PO/请款/变更。
  务必在用户提到项目初始化、新建项目、阶段 0、Skill 0、init_project、绑邮箱、
  项目档案就绪、本地根文件夹路径、或粘贴 [项目初始化] 邮件时使用。
---

# 项目初始化（Skill 0 · project-init）

只把「空项目」立起来；**从 RFP 建包起**归 Skill 1。

| 做 | 不做 |
|----|------|
| `.skill/`、空 Tracker、`项目背景.md`、绑定专用邮箱 | 采购包 / 请款 / 变更 |
| 对话建项：可选进度归档 + 表 B 编排 | 邮件分类（→ **mail-inbox**） |
| 邮局：确认已建 / 挂 pending | handler 里静默建半残项目 |
| 把用户给的授权码写入本地 `.mailbox.secret` | **开邮箱账号**；编造地址；把授权码写入 `project.json` / Git |

**邮箱硬规则**：邮箱须由用户在 163（等）**自行开通**后，把地址（和可选授权码）交给 Agent。禁止声称「已创建邮箱」、禁止编造专用地址。Agent 只会**绑定**已有地址。

## 两条入口

邮局**不会**凭一封初始化邮件直接建项。对话里有人在场，才用 CLI 真正建项。

| 入口 | 何时 | 做什么 | 禁止 |
|------|------|--------|------|
| **A · 对话** | 粘贴初始化邮件 / 口述「新建项目」 | 抽字段 → `init_project.py` → 有进度则表 B | 手搓目录 / 手写 `project.json` |
| **B · 邮局** | `mail-inbox` 分发 `project_init` | `handle_init_email.py`：已建则确认（可回写邮箱）；未建则 `pending` | handler 里静默 `init_project` |

用户要「处理初始化邮件」且给了根路径、意图是建空项目 → **A**；worker/dispatch 自动信 → **B**。拿不准先问根路径。

依赖：基建库 `project-foundation`（`.cursor/lib/`，`init_project.py` / `set_mailbox_secret.py`；**不是 Skill**）；进度 → 表 B；路由 → `mail-inbox`。细则见 `contract-fulfillment-struct/references/mailbox-setup.md`。写 Tracker xlsx 需 `openpyxl`。

## 入口 A · 对话建项

```bash
python3 .cursor/lib/project-foundation/scripts/init_project.py \
  --root "/path/to/project" \
  --name "Sample Project" \
  --code "SAMPLE" \
  --type "实验室" \
  --address "上海市浦东新区 xxx" \
  --client "xxx 有限公司" \
  --pm "张三" \
  --currency "CNY 含税" \
  --mailbox-address "TestProject_AI@163.com"
```

可选：`--schedule-csv`；`--mailbox-secret "授权码"`（一次写入项目根 `.mailbox.secret`，**不会**进 `project.json`）。

| 邮件/对话标签 | CLI | `project.json` | 必填 |
|--------------|-----|----------------|------|
| 项目名称 | `--name` | `project_name` | 是 |
| 项目编号 | `--code` | `project_code` | 是 |
| 项目类型 | `--type` | `project_type` | 是 |
| 项目地址 | `--address` | `address` | 是 |
| 甲方名称 / 甲方 | `--client` | `client_name` | 是 |
| 项目经理 | `--pm` | `project_manager` | 是 |
| 币种/含税 | `--currency` | `currency_tax` | 否（默认 `CNY 含税`） |
| 本地根文件夹路径 | `--root` | `root_path` | 是 |
| 专用邮箱 | `--mailbox-address` | `mailbox.address` | 建议有 |

handler 短键：`client`→`--client`，`pm`→`--pm`，`currency`→`--currency`，`root`→`--root`，`mailbox_address`→`--mailbox-address`。正文模板见 Skill 1 `references/email-templates.md`。

### 授权码（给不会开终端的用户）

推荐：用户在对话里粘贴授权码 → Agent 代写本地文件（用户**不必**自己敲 `echo`）：

```bash
python3 .cursor/lib/project-foundation/scripts/set_mailbox_secret.py \
  --project-root "/path/to/project" \
  --secret "用户粘贴的授权码"
```

或初始化时带上 `--mailbox-secret`。落盘路径固定为 `{项目根}/.mailbox.secret`（chmod 600，并写入项目 `.gitignore`）。  
汇报时只说「已保存授权码」，**禁止**在回复里回显明文。勿把授权码写进邮件模板正文的长期归档（聊天粘贴即可）。

1. 抽字段；缺根路径 / 名 / 编号 → 先问人；缺邮箱则提醒用户先自行开通再提供地址  
2. 跑 `init_project.py`；若用户给了授权码 → `--mailbox-secret` 或 `set_mailbox_secret.py`  
3. **若有** `.mpp` / Project XML / 粗表：归档到 `项目档案/00_进度计划/` → **skill-orchestration 表 B**；无附件则跳过  
4. 汇报根路径、Tracker、邮箱是否已绑、授权码是否已落盘（不回显）；提示可转发 RFP（Skill 1）

进度编排是 **Agent** 责任，不是本 Skill 脚本自动串的。

## 入口 B · 邮局 handler

```bash
python3 .cursor/skills/project-init/scripts/handle_init_email.py \
  --project-root "/path/to/project" \
  --eml "/path/to/msg.eml"
```

| 情况 | 结果 |
|------|------|
| 已有 `.skill/project.json` | `auto` 确认；可回写专用邮箱 |
| 尚无 project.json | `pending`（`project_not_initialized`），不静默建项 |
| 缺根路径 | `project_init_needs_root` → 走入口 A |

pending 后：带抽出字段请 PM 确认，再走 **A** 补建。邮局路径**不**收授权码（勿把密钥放进业务邮件）。

## 完成检查

- [ ] `project.json` 有 `project_name`、`project_code`；空 Tracker + `项目背景.md`  
- [ ] 邮箱地址为用户提供的已开通地址（未编造）；`mailbox.address` 已写  
- [ ] 若用户给了授权码：存在 `{项目根}/.mailbox.secret`，且未写入 `project.json` / 未在回复中回显  
- [ ] 有进度附件则已归档并按表 B 编排（或已说明失败原因）  
- [ ] 未建采购包 / 未改请款或变更台账；已提示可转 RFP  
