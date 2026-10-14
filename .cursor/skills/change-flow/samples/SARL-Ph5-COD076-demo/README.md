# SARL Ph5 · COD076 变更存档样例

最小项目根（Skill 1 Tracker **只读脚手架**）。

输入邮件（已双归档到 `04` + `07`）：
- `变更_COD076_COD.eml` → COD 已发出
- `变更_COD076_PMI.eml` → PMI 已发出

产物：
- `Apple SARL Ph5_change_log.csv` — 变更台账（短标题 + 详细说明、预估金额、COD/PMI 里程碑戳；无「专业」列）
- `Apple SARL Ph5_procurement_packages_status_tracker.csv` — 采购包 Tracker（本 Skill 不改）
- `01_GC_works_Infinity/card-data.json` — 履约卡片数据（**不含**变更；变更只在 Change Log）

重跑示例：

```bash
python3 .cursor/skills/change-flow/scripts/handle_change_email.py \
  --project-root ".cursor/skills/change-flow/samples/SARL-Ph5-COD076-demo" \
  --eml "…/变更_COD076_COD.eml" \
  --route-json "…/.skill/inbox/processed/变更_COD076_COD.route.json"
```
