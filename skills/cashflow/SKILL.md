---
name: cashflow
description: >-
  现金流预测（cashflow）。只读聚合 Tracker、card-data、
  schedule 关键节点与已确认变更，推算供应商侧未来出账（按月）；变更增量默认挂尾款；
  出账滞后默认 30 天。不做收入侧、不写请款/履约/变更数据。务必在用户提到现金流、
  资金计划、出账预测、按月要花多少、现金流预测、cashflow forecast 时使用。
---

# 现金流预测

一句话：**只读**各采购包合同付款条件 + 进度完成日 + 已付账 + 已确认变更，拼出**按月供应商出账预测**。边界见下面「状态口径」。

**全局原则**：先理解再处理（见 `skill-orchestration`）——日期与金额缺一项就进 `pending`，禁止手猜合同额或进度。

## 编排硬规则（摘要）

跨 Skill / 进度 / 合同 PDF / 邮件分发 → 先读 `<skills-root>/skill-orchestration/ALWAYS.md`（细节见同目录 `README.md`）。
单独使用功能 Skill 时禁止擅自串联履约/请款；脚本已串完的不要双跑；时间线对人只有 `项目档案/00_进度计划/关键节点时间线.html` 一份。
`skills-root` = 本机 Skills 安装根（WorkBuddy 常见 `~/.workbuddy/skills/`）。命令写成 `python3 <skills-root>/<技能名>/scripts/…`。

## 状态口径（对人）

| 原则 | 做法 |
|------|------|
| **只看出账** | 供应商付款；不算苹果/JLL 收入；不对接银行/ERP |
| **变更挂尾款** | Change Log「最终确认金额」合计只加在**最后一笔**付款节点（预测用；不读「是否请款」；跳过已取消） |
| **已确认变更列随变更走** | Excel「已确认变更」每次重算：直接读 Skill 3 的 Change Log。变更台账**不加**请款状态 |
| **出账滞后 30 天** | 完成锚点日 + 30 天 = 预计钱离开账户的月份 |
| **只读上游** | 不改 Tracker、card-data、Change Log |

## 界面划分

| 产物 | 归谁 |
|------|------|
| `{项目名}_Cash Flow Forecast.xlsx`、`.skill/cashflow_forecast.json` | **本 Skill** |
| 付款条件、合同金额 | Skill 1 + Tracker |
| 已付账 | Skill 2 → Tracker「下一付款节点」之前的节点 +「已请金额」 |
| 完成时点 | critical-nodes → `window_end` |
| 变更金额 | Skill 3 Change Log（有最终确认金额、非已取消） |

## 权威参考

| 文件 | 何时读 |
|------|--------|
| `references/xlsx-layout.md` | Excel 行列怎么排（给人看的主产物） |
| `references/forecast-schema.md` | JSON 字段、日期/金额规则 |
| `references/overrides.md` | 人工覆盖日期与 lag |
| `scripts/build_forecast.py` | 生成预测真源 |
| `scripts/check_sources.py` | 一键核对台账是否有更新（可重算） |
| `scripts/write_forecast_xlsx.py` | 写出 Excel |
| `samples/demo_project/` | 本 Skill 自带样例；试跑报告写在这里 |

上游（只读）：

- Skill 1：Tracker、`card-data.payment_nodes`
- Skill 2：Tracker「已请金额」+「下一付款节点」（客户批复后才算已请；不读 payment_ledger）
- critical-nodes：`.skill/schedule.json` → `critical_nodes[].window_end`
- Skill 3：`.skill/change_log.csv`（有最终确认金额、非已取消）

## 主路径

```bash
python3 <skills-root>/cashflow/scripts/build_forecast.py \
  --project-root "/path/to/project" \
  --horizon-months 18 \
  --payment-lag-days 30 \
  --write
```

`--write` 写出：

- `{项目名}_Cash Flow Forecast.xlsx`（项目根，主产物；含「检查台账更新」按钮）
- `Check Cash Flow Sources.command`（项目根，按钮会调它）
- `.skill/cashflow_forecast.json`

### 运行参数

| 参数 | 默认 | 说明 |
|------|------|------|
| `--tail-months` | **1** | 项目结束后再留几个月 |
| `--payment-lag-days` | **30** | 完成锚点后多少天计入出账月 |
| `--tax-basis` | `excl_tax` | 主口径不含税 |
| `--as-of` | 今天 | 快照日 `YYYY-MM-DD` |

人工覆盖：`.skill/cashflow_overrides.json`（见 `references/overrides.md`）。

## 逻辑摘要

```text
每包 × 每个付款节点
  → 金额：Tracker 不含税 × 节点比例；最后一笔 + 已确认变更
  → 日期：override → milestone → window_end → schedule_window → 条件推断（PO+N天）
  → 应请月 = 计划锚点 + payment_lag_days；已请完节点用进度窗口日当已发生
```

细则：`references/forecast-schema.md`。

## 与 Skill 1 / 2 / 3 的挂钩

| 对方 | 关系 |
|------|------|
| Skill 1 | 读 Tracker、付款节点 |
| Skill 2 | 读 Tracker 已请 / 下一节点 |
| Skill 3 | 读 Change Log |
| critical-nodes | 读 `window_end` |
| skill-orchestration | 用户要求时才重算 |

**触发**：用户要看现金流；或上游数据更新后用户要求刷新。不要在建包/请款同一回合自动抢跑（除非用户明确要预测）。

## 冒烟

```bash
python3 <skills-root>/cashflow/scripts/smoke_skill4.py
```

样例项目：`samples/demo_project`（只属于本 Skill；报告写在该目录，不写进 Skill 1 / 2）。

## Agent 清单

- [ ] 变更是否只计入**尾款**节点（Change Log 已确认金额）？
- [ ] `payment_lag_days` 是否 30（除非 overrides 或用户指定）？
- [ ] 缺日期/缺金额是否进 `pending` 而非静默猜数？
- [ ] 输出是否含 Excel（`--write`）？
- [ ] 用户要核对台账时是否跑了 `check_sources.py`（有更新再 `--rebuild`）？
