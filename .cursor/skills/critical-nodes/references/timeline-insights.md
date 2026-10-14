# 时间线 · 项目把控区块（insights）

`render_timeline.py` 在生成 HTML 时调用 `timeline_insights.py`，从 **已有** `schedule.json` 推导内容。不新增 Agent 推理步骤。

## 输入真源

| 字段 | 用途 |
|------|------|
| `critical_nodes[]` | 近 30 天清单、待确认、圆点样式 |
| `packages[]` | KPI 包数；缺则回退为 critical_nodes 里的包名 |
| `pending[]` | Agent 吃不准项（原样展示） |
| 系统 `date.today()` | 「今天」竖线、近 30 天窗口起点 |

## 1. 项目锚点竖线

**输出**：时间轴上「今天」竖线（月头可带短标签；悬停见日期）。

| 锚点 | 推断逻辑 |
|------|----------|
| 今天 | 当天落在 `[axis_start, axis_end]` 内则画线 |

（客户验收不单独画竖线：各包验收节点已在行上。）

位置换算与节假日色带一致：按月列等宽，`_date_to_axis_pct(日期, months)`。

## 2. 近 30 天完成

**输出**：列表「日期 · 包 · 节点名 · 来源（明示/倒推/对齐/手工）」；待确认节点标 `?`。

**逻辑**：`window_end ∈ [today, today+30]`，排除 `package_name` 为 `_project` 的旧项目级行（`总包` 行上的公共节点仍可出现在清单）。按日期排序。

## 3. 待确认（倒推 / 对齐）

**目的**：把不是计划明示、且 **尚未被 PM 确认** 的节点摊开，写清依据与定法，并允许当场确认/改日期/删除。

**收录条件**（满足任一，且 `pm_confirmed` 不为 true）：

| 条件 | 含义 |
|------|------|
| `source=inferred` | 相对粗条/邻节点倒推 |
| `source=aligned` | 对齐到邻近锚点 |
| `needs_confirm=true` | 显式标了需确认 |

另：`pending[]` 有内容时一并列出（无操作按钮）。

**每条展示**：

```
包 · 节点名   倒推|对齐  YYYY-MM-DD
依据：……（计划行原文 + 日期）
定法：……（怎么得到 window_end）
风险：risks[]（有则显示）
[确认无误] [改日期] [删除]
```

`basis` 推荐格式：`依据：…｜定法：…`（见 `matching-rules.md`）。解析失败时整段落在「定法」下。

**页面操作**（改完须「保存」下载 JSON → `apply_timeline_edits.py`）：

| 动作 | 效果 |
|------|------|
| 确认无误 | `pm_confirmed=true`，`needs_confirm=false`；列表移除；圆点改实心 |
| 改日期 | 进入编辑并滚到对应圆点，拖动改日 |
| 删除 | 从 `critical_nodes` 删除 |

**圆点样式**：待确认 = 空心（白底 + 包色描边）；已确认/明示/手工 = 实心。

**不做**：按模板查缺「缺到货/缺进场」。

## KPI 条（页头下）

`包数 · 近30天数`（待确认条数在折叠标题上）

## Skill 文档挂钩

- 契约字段：`references/schedule-io.md`
- 必推节点：`references/node-taxonomy.md`
- 视觉：`references/presentation.md` §3–§4
