# 变更邮件阶段识别

主路径：`mail-inbox` 分出 `change.*` → `handle_change_email.py`。  
本文件只写**怎么认**；落账/盖戳细节以脚本 + `change-log-schema.md` 为准。吃不准 → pending。

## 总序

```text
COD 已发出 → PMI 已发出 → 技术审核中 → 技术确认 → 商务确认 → 商务金额确认 → Change PO 下发
                                                                              ↘ 已取消（手改侧枝）
```

- 客户确认 COD **不**单独建状态；确认后发 PMI。
- **先技术、后报价**；顾问终版 ≡ 技术确认。
- 中间扯皮意见：不改当前状态（专用邮箱通常也收不到）。
- **已取消**：PM 手改 Change Log；Skill 3 不靠邮件判取消。已取消后邮件可归档、不推进。

## 识别信号

| 阶段 | intent | 信号（多项命中则更稳） |
|------|--------|------------------------|
| COD | `change.cod` | `COD` / Change Order / 变更确认；可抽序号、短标题、预估（不含税）、时间影响 |
| PMI | `change.pmi` | `PMI` / Project Manager Instruction；收件为总包/供应商 |
| 技术首提 | `change.tech_submit` | 供应商域；submittal / shop drawing / 图纸送审；该序号下首次 |
| 技术确认 | `change.tech_confirm` | 顾问；`approved` / `no further comment` / 终版 / 可据此报价 |
| 商务确认 | `change.commercial` | 转 QS / commercial review / 报价审核；**须已有技术确认** |
| 商务金额确认 | `change.commercial_amount` | CP confirm / 最终金额 / 采购确认报价（非初步询价） |
| Change PO | `change.change_po` | `(Change PO)` / 变更 PO / 增补 PO；**分类真源在 mail-inbox** |

## 关联与 pending

关联优先级：① 变更序号 → ② 明确包名 + 该包唯一未闭环行 → ③ 多/零候选则问人。

| 情况 | 处理 |
|------|------|
| 阶段/角色不清 | pending：`stage_ambiguous` |
| 无序号且多包 | pending：`change_id_unmatched` / `package_unmatched` |
| 技术未结却商务 | pending：`out_of_order` |
| 金额非不含税或抽不出 | pending：`amount_unconfirmed`；禁止自算 |

pending 写入 `.skill/pending.json`：`skill=change-flow`，`step=change_archive`，带 `fields` / `reason` / `eml_path`。只能由 Skill 3 关闭。

## 关键词速查

| 阶段 | 示例 |
|------|------|
| COD | COD, Change Order, 变更确认单 |
| PMI | PMI, Project Manager Instruction |
| 技术首提 | submittal, shop drawing, 图纸送审 |
| 技术确认 | approved, no further comment, 终版 |
| 商务确认 | QS, commercial review, 转报价 |
| 商务金额确认 | CP confirm, final price, 最终金额 |
| Change PO | (Change PO), 变更 PO, 增补 PO |
