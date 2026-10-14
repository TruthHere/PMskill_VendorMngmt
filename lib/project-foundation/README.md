# 项目基建库（project-foundation）

**这不是 Skill。** 不要在对话里当一套技能去调用。  
建项走 Skill 0（`new-project`）；履约 / 请款 / 变更走 Skill 1/2/3。本目录只提供共用文件夹规矩、总表读写和脚本。

**全局原则**：先理解再处理（见 `skill-orchestration`）——共享工具（含报价金额抽取）以附件/原文为准；抽不出不装懂，交给调用方 pending。

## 定位

| 做 | 不做 |
|----|------|
| 阶段 0 初始化（`init_project.py`） | 收邮件、识别 RFP/PO |
| 文件夹 / Tracker / `.skill/` 契约 | 渲染履约卡片（→ `vendor-card`） |
| `common.py` 共享读写与金额工具 | 请款 / 变更状态机 |
| 进度 CSV → `schedule.json` 基础导入 | MPP 解析 / 关键节点推断 |

**调用方**：Skill 0（new-project）、Skill 1（po-flow）、Skill 2、Skill 3、`vendor-card`。`pending.json` 只经 `pending_store.py` 写/关。

真源在仓库 `.cursor/lib/project-foundation/`；安装到 Agent 后与各 Skill **并列**，按 `<skills-root>/project-foundation` 查找。WorkBuddy 安装时仍把本文件夹和各 Skill **并列**放置（脚本按邻居目录查找），但技能列表里不应出现它。

## 权威文档

| 文件 | 内容 |
|------|------|
| `references/folder-rules.md` | 项目根与采购包目录 |
| `references/tracker-schema.md` | Tracker 列与里程碑 |
| `references/tracker-xlsx-theme.md` | Tracker xlsx 样式 |
| `references/schedule-csv-schema.md` | 进度 CSV 表头 |

## 标准命令

对话建项请走 Skill 0；需要直接跑脚本时：

```bash
python3 <skills-root>/project-foundation/scripts/init_project.py \
  --root "/path/to/project" \
  --name "项目名" --code "CODE" \
  --type "…" --address "…" --client "…" --pm "…" \
  --currency "人民币 含税"
```

必填含币种和是否含税，没有默认值。已有 `.skill/project.json` 会拒绝覆盖。建完项目根下有 `待处理邮件/`。这版不要传邮箱。

```bash
python3 <skills-root>/project-foundation/scripts/migrate_project_layout.py \
  --project-root "/path/to/project"
```

```bash
python3 <skills-root>/project-foundation/scripts/schedule_csv.py
# 或经 Skill 1 import_schedule_csv.py 薄封装
```

## 脚本一览

| 脚本 | 用途 |
|------|------|
| `common.py` | Tracker / JSON / 金额 / 路径 / 付款 enrich 工具 |
| `pending_store.py` | `.skill/pending.json` 唯一写入口：必须带 skill，只能关自己的 |
| `write_guard.py` | 对话路径写权限：用错 Skill 拒写 Tracker / 卡片 / Change Log |
| `init_project.py` | 阶段 0。必填含 `--currency`（币种 + 是否含税）。生成 `待处理邮件/`。已建过则拒绝。这版不问邮箱 |
| `install_orchestration_rule.py` | 把 `skill-orchestration/ALWAYS.md` 写入 `{项目根}/.codebuddy/rules/pm-skill-orchestration/RULE.mdc` |
| `set_mailbox_secret.py` | 对话友好：写入项目根 `.mailbox.secret` |
| `tracker_xlsx.py` | Tracker 配套 xlsx |
| `schedule_csv.py` | 进度 CSV ↔ `schedule.json` |
| `migrate_project_layout.py` | 旧布局迁移 |

## 和业务 Skill 的关系

| 本库 | Skill 1 | vendor-card |
|------|---------|------------------|
| 项目骨架与数据契约 | 邮件履约编排 | 读 `card-data` / schedule 渲染 HTML |
