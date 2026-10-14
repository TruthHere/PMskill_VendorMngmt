# 请款申请页与模板字段

**真源 Skill**：`payment-sheet`（本文件所在）。Skill 2 只消费页 / Excel 并入账（回写台账请款章节）。供应商填单 ≠ 公司入账。

## 产出文件

```
{package_dir}/
  履约条件卡片.html     # vendor-card；含「发起请款」链接
  请款申请.html         # payment-sheet（渲卡片后自动刷，也可单独 sync）
  .claim-assets/        # payment-sheet：JSZip + 填表脚本 + 模板副本
```

公司模板：

- 项目已认过客户表：`{项目根}/.skill/payment-sheet/template.xlsx` + `template-profile.json`
- 还没认：**请款单生成未启用**。填写页只显示提醒。不要拿技能自带样例或别的项目的表来充数。

换业主必须先做认模板（`references/template-profile.md`）。格子对照只认**本项目**那份对照表。

## 已请 / 金额口径

- 请款金额默认不含税；客户模板写含税则按含税填、页上标明。**不按比例代算**。
- 本页不展示台账「已请金额 / 待请款金额 / 下一付款节点」，付款节点表不标「已请」「本笔」。
- 网页不预填 PO、不读历史填表当草稿。下载 Excel 时用 Tracker「已请金额」合成既往行（不再读 payment_ledger）。

## 字段从哪来

**只认本项目** `.skill/payment-sheet/template-profile.json`（网页字段 → Excel 哪一格）。  
认模板时对照用户交来的那张客户请款单起草，用人话念一遍再落盘。  
禁止拿别的业主、别的项目、技能自带样例的格子当默认。

预填数据仍来自 `card-data` / 台账 / `project.json`（项目名、供应商、合同额、付款节点摘要等）；供应商抬头（PO、联系人、本次金额）以对照表 `form.user_fields` 为准，不预填 PO。  
审批签字栏、公式格：不要映射、不要覆盖。  
「本期是否含变更」只在请款页给人复核，是否写入 Excel 看对照表；入账写入 ledger `variations_included`。

支持文件 Checklist 只作提醒，不进 Excel（除非对照表声明要写格子）。随所选节点变化：预付款无需附件；到货款提示到货签认单；验收款提示验收确认单。发票一律提示「客户批复请款后再开发票」。

**边界**：变更台账（Skill 3）**不加**「是否请款」列；变更与请款流程分开。

## 页面行为

1. 打开 `请款申请.html`（本地即可）
2. 选择节点 → 随单附件提示跟着变（预付无附件 / 到货签认单 / 验收确认单；发票：客户批复请款后再开）
3. PAYMENT NO 随节点变化，显示在页眉；金额栏空白，提示「须为不含税，自行填写」
4. 主按钮下载客户模板 `.xlsx`（**ZIP 只改格子里的字**，图/换行/合并一比一。禁止整表重写）
5. 可选：CLI `generate_payment_application.py` 从 JSON 再出一份（只出 Excel，不入账）
6. **入账**：客户批复后 → Skill 2 回写台账请款四列（与本页拆开）

## claim_response.json 键

与 `fill_payment_application.py` 一致：`payment_no`、`project_name`、`division`、`division_code`、`billing_entity`、`vendor_name`、`work_package`、`vendor_ref`、`po_number`、`po_value_excl_tax`、`contract_value_excl_tax`、`contact_name`、`contact_mobile`、`office_phone`、`office_address`、`claim_node`、`claim_amount_excl_tax`、`includes_variations`（bool，本期是否含变更）、`variations_to_date`、`period_count`、`previous_claims`、`nodes_overview`、`vat_note_pct`、`notes`、`support_files`。
