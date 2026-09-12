# 履约卡片（fulfillment-card）判卷规则

本 Skill 只负责把 `card-data.json` 印成 `履约条件卡片.html`。  
判卷也只考「印得对不对 / 印得好不好」，**不考**建包、邮件、Tracker（那是 Skill 1）。

运行：

```bash
python3 .cursor/skills/fulfillment-card/scripts/run_all_evals.py
# 产物：fulfillment-card-workspace/iteration-N/review.html
```

---

## 两层分数（必须分开看）

| 层级 | 代号 | 含义 | 当前 Skill 是否强制 |
|------|------|------|---------------------|
| **格式** | `format` | 长得像标准卡片（页眉/表格/页脚/总包约束开关） | 是（不过则**拒出卡**） |
| **内容质量** | `quality` | 数据够不够清晰（中英节点、比例、含税等） | 是（**软提醒**：仍出卡，但必须识别并提示） |

- **格式不过** → 渲染失败，优先修模板/渲染脚本。  
- **质量不过** → **仍出卡**，但必须：`quality_ok=false`、`card-data.quality_warnings[]` 有条目、卡片顶部显示「数据质量提醒」。  
- 总通过率只作概览；精调时以 **format / quality 分行** 为准。

---

## A. 格式硬规则（`format`）

凡「有卡片 HTML」的考题都必须查：

| # | 断言（英文短句，写入 grading.json） | 人话 |
|---|--------------------------------------|------|
| F1 | `card HTML exists` | 产出了 `履约条件卡片.html` |
| F2 | `card-data.json exists` | 有机读真源 |
| F3 | `card-title is supplier_name` | 大标题是**供应商**，不是采购包名 |
| F4 | `package-name appears in subtitle` | 副标题有采购包名 |
| F5 | `payment nodes render as payment-table` | 付款是表格，不是手写段落 |
| F6 | `card has no change section` | 履约卡**不**再展示变更（变更只在 Change Log） |
| F7 | `data_sources live in footer-meta` | 「数据来源」只在页脚 |
| F8 | `claim link points to 请款申请.html` | 右上角「发起请款」链到同包请款页 |
| F9 | `no unresolved template placeholders` | 没有残留 `{{…}}` |
| F10 | `validate_rendered_card passes` | 与脚本内置格式校验一致 |
| F11 | `GC shows 约束条款 section` | **仅**总包考题：有「约束条款」章节 |
| F12 | `non-GC hides 约束条款 section` | **仅**非总包：即使 data 里写了约束文字，HTML 也不出该章节 |
| F13 | `payment_attachments appear in table` | 节点带了附件清单时，表里能看见 |
| F14 | `empty payment_nodes show 待补充 row` | 无节点时表格空态为「待补充」 |

---

## B. 内容质量规则（`quality`）

好数据的考题应过；故意烂数据的诊断题用来证明「判卷能抓住质量问题」。

| # | 断言 | 人话 | 判定要点 |
|---|------|------|----------|
| Q1–Q6 | 供应商/中英节点/比例/含税/附件/计划列 | 数据本身是否合格 | 见 `grade_card.py` |
| Q8 | 好数据无提醒 | `quality_ok` + 无横幅 | 达标题 |
| Q9 | 烂数据有提醒且横幅在页眉**之上** | warnings + banner | 诊断题；**不进 pending** |

`card_quality.py` 另查：对接人邮箱、验收标准、范围、交期、合同号/签约日、节点触发条件空、总包「施工进度 N」占位。

实现：`scripts/card_quality.py` → `render_card.py` 写入 `quality_warnings` / `quality_ok`，并注入卡片横幅。

---

## C. 考题清单（与 `evals.json` 对齐）

| id | name | 测什么 | 期望 |
|----|------|--------|------|
| 0 | `supply-good` | 合格纯供应全字段 | format + quality 都应过；无提醒横幅 |
| 1 | `gc-constraint` | 总包约束章节 | format（含 F11）过；无提醒 |
| 2 | `non-gc-hides-constraint` | 非总包不出约束 | F12 必须过；无提醒 |
| 3 | `attachments-infer` | 未手写附件 → 启发式补全 | F13 + Q5；无提醒 |
| 4 | `no-change-on-card` | 即使 card-data 有旧 change_items 也不出变更章 | F6；无提醒 |
| 5 | `quality-gap` | **故意烂数据** | format 过；**必须** `quality_ok=false` + warnings + 横幅 |

`quality-gap` 单独标成诊断题。汇总时：

- **达标分** = eval 0–4（好数据：干净出卡、无误报提醒）  
- **诊断分** = eval 5（烂数据：仍出卡 + 提醒到位）

---

## D. 对照基线（without_skill）

不用本 Skill 时：手写一段「像卡片」的 HTML/TXT（采购包当标题、无表格、无页脚来源）。  
应用**同一套**断言，预期大量 format 失败 → 用来证明「有 Skill / 无 Skill」能拉开差距。

---

## E. 明确不考（避免和别的 Skill 抢分）

- 是否从邮件抽出付款节点（Skill 1）  
- Tracker / `.eml` 归档（Skill 1）  
- 请款申请页内容对不对（归 **payment-form**；本 Skill 只要求「发起请款」链存在）  
- Change Log 状态机与金额（Skill 3；本 Skill **不**展示变更）  
- 进度计划日期算得准不准（schedule-*；有 `schedule_window` 时只考有没有印出来）

---

## F. 与后续精调的关系

1. 质量提醒已落地（软门禁）：烂数据可出卡，但必须提示。  
2. 提醒**只在卡片顶栏**；不进 `pending.json`。  
3. 每改一轮重跑 `run_all_evals.py`；达标题勿误报提醒，诊断题必须有提醒。
