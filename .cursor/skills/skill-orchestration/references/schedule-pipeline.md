# 进度计划编排（系统内强制调用链）

**服从**上级 [`../SKILL.md`](../SKILL.md)。  
凡出现进度计划（`.mpp` / Project XML / 甘特 / Master Schedule）且在**供应商履约系统内**处理时，禁止不读进度瞎猜日期。

> 用户只要「转 Excel」或「析关键节点」、未提履约/请款 → 走功能 Skill **单独使用**，不必跑到 fulfillment-card。

## 强制链路（系统内 · 按顺序）

```text
.mpp / Project XML
  → ① schedule-mpp-excel
       产出：项目档案/00_进度计划/*_schedule.csv
            + *_project_view.xlsx（给人看）
  → ② schedule-critical-nodes（Agent 主导）
       Agent 读懂表 → 按包推理 critical_nodes
       → write_critical_nodes.py 校验落盘
       → .skill/schedule.json + 可选时间线 HTML
  → ③ fulfillment-card
       读 schedule.json / critical_nodes
       → enrich 付款节点 schedule_window
       → render_card.py（履约卡片 → 自动 payment-form 刷请款页）
```

已是 `.csv` / `.xlsx` 任务表时：可跳过 ①，从 ② 开始。

`analyze_schedule.py` 字典草稿**不是**本链路的默认步骤。

## 采购包录入时的再次同步（脚本编排 · 表 A）

每录入一个采购包（`add_package` / RFP）由**脚本**调用：

`schedule-critical-nodes/scripts/sync_schedule_timeline.py`

行为：**若已有 `critical_nodes` → 只重渲时间线 HTML，不重跑分析、不覆盖 Agent 节点。**  
尚无节点 → `skipped: no_critical_nodes`（提示走 Agent 主路径；勿在建包回合用字典 analyze 顶替，除非显式 `--draft-analyze`）。

Agent **不要**在建包成功后同一回合再手动 analyze 覆盖节点。

产出：

1. 项目级 `项目档案/00_进度计划/关键节点时间线.html`
2. `{采购包目录}/关键节点时间线.html`（该包过滤视图）

无进度源时软跳过，不阻断建包。

## Agent 必读 Skill

| 顺序 | 路径 | 职责 |
|------|------|------|
| ① | `.cursor/skills/schedule-mpp-excel/SKILL.md` | MPP→CSV/甘特 Excel |
| ② | `.cursor/skills/schedule-critical-nodes/SKILL.md` | **理解**进度 → 采购包×关键节点 → `write_critical_nodes` |
| ③ | `.cursor/skills/fulfillment-card/SKILL.md` → `payment-form` | 卡片；自动刷请款页 |

## 禁止事项

- ❌ 因「本机没有 Java」放弃 MPP（应走 mppjs 或另存 XML）
- ❌ 只把 `.mpp` 归档却不调用 ①②（系统内）
- ❌ 不读进度表就编造完成日写入 `schedule.json`
- ❌ 把 `analyze_schedule` 关键词草稿直接当定稿
- ❌ 跳过 `schedule-critical-nodes` 直接把粗 CSV 当请款完成时点
- ❌ 把进度 `pending` 写进项目 `.skill/pending.json`（进度待确认只留在 `schedule.json`；脚本会硬拦）

## 与付款节点的关系

- 合同/邮件决定 **付款节点名称与比例**
- `critical_nodes` 决定 **计划完成时点**（优先 `window_end`）
- 二者在 **fulfillment-card** 对齐；没有 schedule 基座时不要假装已对齐
