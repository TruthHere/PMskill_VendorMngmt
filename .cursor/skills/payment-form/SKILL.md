---
name: payment-form
description: >-
  辅助 Skill：请款申请页与公司模板 Excel（payment form）。读 card-data.json 与台账合同不含税额，
  写出同包「请款申请.html」；页内一键下载 Apple Payment Application xlsx；CLI 可同规则填模板。
  不估算本次请款金额、不入账、不改 Tracker、不渲染履约卡片。
  被 fulfillment-card（渲卡片后自动刷页）调用。网页不展示已请；下载 Excel 时可读 ledger
  填既往请款行。务必在用户提到请款申请页、payment form、
  payment-form、下载请款单 Excel、Apple_Payment_Application、精调请款表单/请款申请 HTML 时使用。
disable-model-invocation: true
---

# 请款申请页（payment-form · 辅助 Skill）

**全局原则**：先理解再处理（见 `skill-orchestration`）——只消费上游已写入的 `card-data` 与台账请款章节，不臆造金额。

请款金额**一律不含税**。本次请多少由供应商自己填；本 Skill **不按比例代算**，避免系统数和人手对不上。

本页**不展示**台账「已请 / 待请 / 下一节点」，也不标「已请」「本笔」。合同额仍从台账「金额不含税」带出。入账仍归 Skill 2。

## 定位

| 做 | 不做 |
|----|------|
| `card-data` + 台账请款章节 → `请款申请.html` | 渲染 `履约条件卡片.html`（归 `fulfillment-card`） |
| 页内按钮 → 公司模板 `.xlsx`（只改文字、版式一比一、不要第二张表） | 请款提醒 / 入账 / 回写 Tracker（归 Skill 2） |
| CLI 按同一规则填 `Apple_Payment_Application.xlsx` | 从邮件抽付款条件（归 Skill 1）；用 ledger 锁定 PO / 联系人 |
| 写入包内 `.claim-assets/`（JSZip + 模板副本） | 写 Change Log；把填表底稿塞进财务入账 |

精调「请款页 / 出 Excel」→ **本 Skill**；精调「履约卡片」→ `fulfillment-card`；精调「入账流程」→ Skill 2。供应商填单和公司记入这笔请款是两件事，不要混。

## 已请口径（网页不展示，Excel 要带上）

采购包状态台账仍有「请款」三列，给 Skill 2 入账用。请款申请页不画「已请 / 本笔」，也不预填 PO。

下载 Excel 时：既往请款优先用 Tracker「已请金额」合成一行；不读 payment_ledger（已废除）。不按比例代算。

`Period`（P23）= 付款节点个数。`Variations to-date`（I30）= Change Log 同包「最终确认金额」合计（跳过已取消）。`exclude xx% VAT` 由**本包**台账「金额含税 ÷ 金额不含税」算出（各包可以不同）；两列缺一侧就不写，不拿项目档案的税率凑。

## 与相邻 Skill

| 谁 | 关系 |
|----|------|
| **Skill 1** | 写干净 `card-data` → 调 `fulfillment-card`；卡片渲染会**自动**调本 Skill 刷请款页 |
| **fulfillment-card** | 只出履约卡片；渲完后调用本 Skill（`did` 含 `payment-form.sync`） |
| **Skill 2** | 客户批复后回写台账请款三列；消费本 Skill 产出的页 / Excel |
| **本 Skill** | 拥有请款页模板、公司 Excel 模板、填表规则 |

系统内：改完 `card-data` 并跑 `fulfillment-card/render_card.py` 后，**不要**再手跑本 Skill（除非 `claim_form_path` 缺失补救，或用户只要刷请款页）。

单独使用：用户只要重刷请款页 / 精调页与 Excel → **只**跑本 Skill，勿改履约卡片业务数据。

本页 HTML 按 **苹果 Payment Application** 定制（换业主换模板）。供应商名 / 项目 / 合同额由履约卡片与台账带出；PO 与抬头由供应商自填。

## 权威文档

- `assets/claim-form.html` — 请款申请页 HTML 真源
- `assets/Apple_Payment_Application.xlsx` — 公司请款单模板（唯一真源）
- `assets/fill-apple-xlsx.js` + `assets/vendor/jszip.min.js` — 页内按 ZIP 填格子，不重写版式
- `references/claim-form.md` — 字段分工与格子映射
- `scripts/sync_claim_form.py` — 刷请款页
- `scripts/fill_payment_application.py` / `generate_payment_application.py` / `patch_apple_xlsx.py` — CLI 填模板（ZIP 补丁，版式一比一）

## 标准命令

只刷请款页：

```bash
python3 .cursor/skills/payment-form/scripts/sync_claim_form.py \
  --package-dir "/path/to/{序号}_{采购包}_{供应商}/"
```

CLI 出 Excel（与页内规则一致；只出文件，不入账）：

```bash
python3 .cursor/skills/payment-form/scripts/generate_payment_application.py \
  --response "/path/to/claim_response.json" \
  --package-dir "/path/to/01_xxx_Vendor" \
  --out-dir "/path/to/output"
```

## 输出

| 产物 | 说明 |
|------|------|
| `请款申请.html` | 同包可打开填表；主按钮「下载苹果请款单（Excel）」 |
| `.claim-assets/` | JSZip + 填表脚本 + 模板副本（给浏览器离线填） |
| CLI `.xlsx` | 填好的公司请款单（不是财务底稿） |

`sync_claim_form` 成功时 stdout 为请款页路径。经 `fulfillment-card` 调用时，返回 JSON 里会有 `claim_form_path`，`did` 含 `payment-form.sync`。

## 禁止

- ❌ 手改包内 `请款申请.html`（改真源 `assets/claim-form.html` 后重跑 sync）
- ❌ 按节点比例代算本次请款金额
- ❌ 用 ledger / 历史填表来锁定 PO、联系人
- ❌ 在本 Skill 写 ledger / 改 Tracker 请款章节
- ❌ 把出 Excel 逻辑写回 Skill 2 或 fulfillment-card

总规则：`.cursor/skills/skill-orchestration/SKILL.md`。
