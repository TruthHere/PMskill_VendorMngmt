# 请款申请页与模板字段

**真源 Skill**：`payment-form`（本文件所在）。Skill 2 只消费页 / Excel 并入账（回写台账请款章节）。供应商填单 ≠ 公司入账。

## 产出文件

```
{package_dir}/
  履约条件卡片.html     # fulfillment-card；含「发起请款」链接
  请款申请.html         # payment-form（渲卡片后自动刷，也可单独 sync）
  .claim-assets/        # payment-form：JSZip + 填表脚本 + 模板副本
```

公司模板唯一真源：

`.cursor/skills/payment-form/assets/Apple_Payment_Application.xlsx`

## 已请 / 金额口径

- 请款金额**一律不含税**。本次请多少由供应商自填，**不按比例代算**。
- 本页不展示台账「已请金额 / 待请款金额 / 下一付款节点」，付款节点表不标「已请」「本笔」。
- 网页不预填 PO、不读历史填表当草稿。下载 Excel 时用 Tracker「已请金额」合成既往行（不再读 payment_ledger）。

## 字段分工（Apple Payment Application · Invoice）

### 预填（台账 / card-data / project.json）

| 模板格 | 来源 |
|--------|------|
| C2 Project | `card-data.project_name` |
| C3 Division | `project.json` → `division`（缺则空） |
| C4 / C11 Vendor | `supplier_name` |
| C5 Work Package | `package_name` |
| C7 PO Number | 供应商自填（不从卡片带出） |
| C8 / C9 / I29 | 台账「金额不含税」（没有就空，不用含税字样去除税） |
| D8 / D9 VAT 文案 | 本包台账「金额含税 / 金额不含税」算出的税率，写成 `(CNY exclude xx% VAT)`；缺一侧则留空，不用项目级默认 9 |
| B19 / C19 | `project.json.division_code` / `billing_entity`（缺则空，清掉模板演示字） |
| B22 节点总览 | `payment_nodes` 文本摘要 |
| B1 / Q19 PAYMENT NO | 当前第几笔（所选付款节点） |
| P23 Period | 付款节点总个数（3 个节点就是 3，不是第几笔） |
| I30 Variations to-date | Change Log 同包「最终确认金额」合计（已取消不计；没有就是 0） |
| 明细行 36 起 | 既往请款（ledger 里早于本笔的 **certified / 客户已批复**）；本次写在其后一行 |
| Q39 Total Invoice Value | 公式 `SUM(Q36:本次行)`，含既往 + 本次 |
| Q41 Less Payment Previously Certified | 既往请款金额之和 |
| Q45 Total Claim | 公式 `Q39-Q41`（也就是本次） |

### 供应商填（苹果请款单抬头）

| 字段 | Excel | 说明 |
|------|-------|------|
| PO Number | C7 | 必填；灰字占位，不预填 |
| Vendor Reference Number | C6 | 必填；PO 上的供应商编号 |
| 联系人 Contact Point | C12 | 必填 |
| 手机 Contact Number | C13 | 必填 |
| 公司电话 Office | C14 | 可空 |
| 公司地址 Office Address | K12 | 必填 |
| 本次请款节点 | 本次明细行 B 列 | 下拉；默认第一笔，不按台账「下一节点」预选 |
| 本次请款金额（不含税） | 本次明细行 Q 列 | 供应商自填，系统不代填；页内按货币格式显示（CNY 300,000.00），写入 Excel 仍是数字 |
| 本期是否含变更 | 不进苹果 Excel | 勾选即可；只给人复核，不拆变更金额。入账写入 ledger `variations_included`（true/false） |

支持文件 Checklist 只作提醒，不进 Excel。随所选节点变化：预付款无需附件；到货款提示到货签认单；验收款提示验收确认单。发票一律提示「客户批复请款后再开发票」。备注栏苹果模板没有，本页不收集。

**边界**：变更台账（Skill 3）**不加**「是否请款」列；变更与请款流程分开。本勾选只属于请款页 / 请款入账。

### 留空

审批栏 Signature / Date / Project Manager。

Advance Payment Schedule 表：下载时删除，只留 Invoice。I29 / I31 / Q39 / Q45 保留模板公式（插既往行后公式行号跟着下移），不手写覆盖。

## 页面行为

1. 打开 `请款申请.html`（本地即可）
2. 选择节点 → 随单附件提示跟着变（预付无附件 / 到货签认单 / 验收确认单；发票：客户批复请款后再开）
3. PAYMENT NO 随节点变化，显示在页眉；金额栏空白，提示「须为不含税，自行填写」
4. 主按钮「下载苹果请款单（Excel）」按公司模板下载 `.xlsx`（版式一比一，无第二张表）
5. 可选：CLI `generate_payment_application.py` 从 JSON 再出一份（只出 Excel，不入账）
6. **入账**：客户批复后 → Skill 2 回写台账请款三列（与本页拆开）

## claim_response.json 键

与 `fill_payment_application.py` 一致：`payment_no`、`project_name`、`division`、`division_code`、`billing_entity`、`vendor_name`、`work_package`、`vendor_ref`、`po_number`、`po_value_excl_tax`、`contract_value_excl_tax`、`contact_name`、`contact_mobile`、`office_phone`、`office_address`、`claim_node`、`claim_amount_excl_tax`、`includes_variations`（bool，本期是否含变更）、`variations_to_date`、`period_count`、`previous_claims`、`nodes_overview`、`vat_note_pct`、`notes`、`support_files`。
