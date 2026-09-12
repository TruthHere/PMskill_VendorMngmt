# Schedule I/O 契约（下游 Skill 必读）

本 Skill 的**唯一结构化真源**是项目内：

```
{project_root}/.skill/schedule.json
```

**写入主路径**：Agent 推理出 `critical_nodes` 后，经 `write_critical_nodes.py` 校验落盘（可带 `--write-md` / `--write-timeline`）。  
`analyze_schedule.py` 仅可选草稿，不得当作已理解进度。

可选人类可读摘要：

```
{project_root}/.skill/critical_nodes.md
```

可视化时间线（`render_timeline.py` / `write_critical_nodes.py --write-timeline`）：

```
{project_root}/项目档案/00_进度计划/关键节点时间线.html
{project_root}/.skill/critical_nodes_timeline.html
{package_dir}/关键节点时间线.html   # 建包后 sync 只重渲，不覆盖节点
```

下游 Skill（履约、请款）**只读本契约**，不要自行从粗甘特「发明」节点。

## `schedule.json` 顶层

| 字段 | 类型 | 说明 |
|------|------|------|
| `milestones` | array | 原计划归一化任务行（兼容 Skill 1 旧导入） |
| `critical_nodes` | array | 按包展开后的关键节点（本 Skill 主产出） |
| `pending` | array | 需 PM 确认项（**只写本文件**；禁止写入项目 `.skill/pending.json`） |
| `packages` | array | 本次分析使用的采购包清单快照 |
| `source_file` | string | 相对或绝对路径 |
| `analyzed_at` | string | ISO8601 |
| `analysis_mode` | string | 可选；Agent 落盘为 `agent` |
| `imported_at` | string | 可选；仅 CSV 导入时保留 |
| `note` | string | 可选说明 |

### `milestones[]` 行（兼容）

| 字段 | 说明 |
|------|------|
| `name` | 任务/里程碑名（可含包名前缀） |
| `date` | 开始日 `YYYY-MM-DD` |
| `end_date` | 可选结束日 |

### `critical_nodes[]` 行

| 字段 | 必填 | 说明 |
|------|------|------|
| `node_code` | ✅ | 见 `node-taxonomy.md` |
| `name` | ✅ | 展示用，建议 `中文 / English` |
| `name_zh` | 推荐 | 中文名 |
| `name_en` | 推荐 | 英文名 |
| `window_start` | ✅ | `YYYY-MM-DD`（任务/推断窗口起点；展示工期时可用） |
| `window_end` | ✅ | `YYYY-MM-DD`（**完成日**；请款触发、时间线圆点优先用此字段） |
| `source` | ✅ | `explicit` \| `inferred` \| `aligned` \| `manual`（PM 时间线/手工调整） |
| `confidence` | ✅ | 0–1 数字 |
| `basis` | ✅ | 人可读依据。倒推/对齐推荐：`依据：计划行…｜定法：…`（勿写「缺什么」） |
| `package_name` | ✅* | 包名；项目级用 `_project` |
| `package_type` | ✅* | `供应` / `供装` / `顾问` / `总包` / `_project` |
| `risks` | 可选 | string 数组 |
| `needs_confirm` | 可选 | bool；true 时下游应谨慎录用 |
| `pm_confirmed` | 可选 | bool；PM 在时间线「确认无误」后为 true；待确认列表不再收录 |

\* 项目级节点：`package_name=_project`，`package_type=_project`。

### `pending[]` 行

| 字段 | 说明 |
|------|------|
| `code` | 如 `unmapped_task` / `low_confidence` / `missing_anchor` |
| `message` | 问 PM 的文案 |
| `context` | 可选对象（任务名、包名等） |

## 下游如何录用（履约 / 请款）

1. 读 `.skill/schedule.json`
2. 若存在非空 `critical_nodes`：
   - 按 `package_name` + `node_code`（或付款语义映射）取窗口
   - **请款 / 完成时点对齐优先用 `window_end`**；`window_start`～`window_end` 仅表示计划作业跨度
   - 付款表 `schedule_window`：完成导向可用 `≤ YYYY-MM-DD`（取 end）；需要跨度时再用 `start ~ end`
3. 若无 `critical_nodes`：不要用粗甘特瞎填请款日；走本 Skill（Agent）补节点，或标未对齐

付款语义 → `node_code` 映射见 `node-taxonomy.md`「与付款语义对齐」。

对人汇报、时间线 HTML、旬粒度等见 **`presentation.md`**（强制）。

## 输入文件

| 格式 | MVP |
|------|-----|
| `.csv` / `.xlsx` | ✅ 直接解析 |
| `.mpp` / Project XML | 先经 `schedule-mpp-excel` 生成 `*_schedule.csv`，再解析 |
| PDF | 第二迭代（经 pdf-read 抽表） |

表头别名与 [`project-foundation/references/schedule-csv-schema.md`](../../../lib/project-foundation/references/schedule-csv-schema.md) 对齐。

采购包清单来源（优先级）：

1. CLI `--packages-json` / `--packages-csv`
2. 项目 Tracker CSV（`package_name` / `package_type` 列）
3. 仅进度表内出现的包名（类型默认 `供应`，并 `pending` 提示确认类型）

## 幂等与合并

- Agent 经 `write_critical_nodes.py` 再次落盘会 **重写** `critical_nodes` / `pending` / `analyzed_at`
- 有 `--source` 时刷新 `milestones`；否则保留已有 `milestones`
- 建包 `sync_schedule_timeline` **不**重写 `critical_nodes`（只重渲 HTML）
- 不删除无关顶层字段（若他 Skill 写入额外键，尽量保留）

## Markdown 摘要格式（可选）

须按**请款序 + 完成旬**书写（不要把工期长条当成单一请款节点）：

```markdown
# 关键节点摘要
分析时间: ...
源文件: ...

## BMS（供装）
1. 到货 / Delivery · 完成 2026-10-31（2026年10月下旬）| inferred | ...
2. 安装完成 / Installation Complete · 完成 2026-11-21（2026年11月下旬）| explicit | ...
3. 验收 · 完成 2027-01-19（2027年1月中下旬）| ...

## Pending
- ...
```

ISO 日便于机器；括号内旬描述便于人读。换算规则见 `presentation.md` §2。