---
name: new-project
description: >-
  业务 Skill 0 · 项目初始化。新建项目根、.skill/project.json、空 Tracker、项目背景、
  绑定专用邮箱；可选归档进度计划并编排 mpp-to-excel → critical-nodes。
  不建采购包、不做 RFP/PO/请款/变更。务必在用户提到项目初始化、新建项目、阶段 0、
  Skill 0、init_project、绑邮箱、项目档案就绪时使用。
disable-model-invocation: true
---

# 项目初始化（Skill 0 · new-project）

## 定位

| 做 | 不做 |
|----|------|
| 建项目目录与 `.skill/`、空 Tracker、`项目背景.md` | 录入采购包（→ **Skill 1**） |
| 写入专用邮箱配置（IMAP 地址等） | 请款 / 变更 |
| 可选：归档进度计划并触发进度编排 | 邮件日常分类（→ **mail-inbox** 契约） |

**边界**：Skill 0 只把「空项目」立起来；**从 RFP 建包起**归 Skill 1。

## 依赖

| 依赖 | 用途 |
|------|------|
| 基建库 `project-foundation`（`.cursor/lib/`，不是 Skill） | `init_project.py`、文件夹/Tracker 契约 |
| `mpp-to-excel` / `critical-nodes` | 初始化时若带 Master Schedule（Agent 编排） |
| `mail-inbox` | 意图 `project_init` 路由到本 Skill（契约已立） |

Python：`.cursor/lib/project-foundation/requirements.txt`（写 Tracker xlsx 需 `openpyxl`）。WorkBuddy 受管 venv 缺包时先 `pip install -r …/project-foundation/requirements.txt`。

## 邮件入口（Skill 0 handler）

`mail-inbox` 将 `project_init` 分发到本 Skill：

```bash
python3 .cursor/skills/new-project/scripts/handle_init_email.py \
  --project-root "/path/to/project" \
  --eml "/path/to/msg.eml"
```

行为：

| 情况 | 结果 |
|------|------|
| 项目已有 `.skill/project.json` | `auto` 确认；正文含专用邮箱时可回写绑定 |
| 目录尚无 project.json | 写 `pending`（`project_not_initialized`），**不**静默建项目 |
| 缺 project_root / 根路径 | 返回原因，提示用 `run_init.py` 手工初始化 |

邮箱授权码与拉取 worker：见 `po-flow/references/mailbox-setup.md`（绑定动作在本 Skill 初始化时完成）。

## 标准命令（新建空项目）

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

可选：`--schedule-csv /path/to/schedule.csv` 在初始化时导入进度里程碑。

本 Skill 薄封装（等价调用）：

```bash
python3 .cursor/skills/new-project/scripts/run_init.py \
  --root "/path/to/project" \
  --name "Sample Project" \
  --code "SAMPLE" \
  --type "实验室" \
  --address "…" --client "…" --pm "…" \
  --currency "CNY 含税" \
  --mailbox-address "…"
```

## 工作流

1. 从初始化邮件或对话提取：项目名、代码、类型、地址、客户、PM、币种、邮箱  
2. 运行 `init_project`（foundation）  
3. 配置授权码（见 mailbox-setup；**勿提交 Git**）  
4. 若有 `.mpp` / 进度表：归档到 `项目档案/00_进度计划/` → 按 `skill-orchestration` **表 B** 跑 mpp-excel → critical-nodes（本 Skill 负责在初始化场景触发，不手猜日期）  
5. 汇报：项目根、Tracker 路径、邮箱是否已绑；提示「可开始转发 RFP（Skill 1）」

## 与兄弟 Skill

| Skill 0 | Skill 1 | Skill 2 | Skill 3 |
|---------|---------|---------|---------|
| 空项目就绪 | 建包起履约 | 请款 | 变更 |

字段示例见 Skill 1 `references/email-templates.md` 中「项目初始化」段（共享模板，不复制业务）。
