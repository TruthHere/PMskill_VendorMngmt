# mail-inbox 意图表（Intent Taxonomy）

分类只回答：**这封信交给哪个业务 Skill、哪类动作**。不在此层写 Tracker / Change Log。

## 优先级（从上到下，先匹配先生效）

RFP 正文常夹带「请款条件」——**不得**因此改判为付款专信。  
不做 `change.noise`（专用邮箱收不到中间意见；PM 只转关键/终态）。

| 序 | intent | 路由到 | 说明 |
|----|--------|--------|------|
| 1 | `project_init` | Skill 0 | 建项目根 / Tracker / 邮箱绑定 |
| 2 | `change.change_po` | Skill 3 | Change PO |
| 3 | `change.cod` | Skill 3 | COD 已发出 |
| 4 | `change.pmi` | Skill 3 | PMI 已发出 |
| 5 | `change.tech_submit` | Skill 3 | 供应商技术文件首提 |
| 6 | `change.tech_confirm` | Skill 3 | 顾问终版 → 技术确认 |
| 7 | `change.commercial` | Skill 3 | 商务确认（未到金额） |
| 8 | `change.commercial_amount` | Skill 3 | 商务金额确认 / CP Confirm |
| 9 | `fulfillment.rfp` | Skill 1 | RFP/RFQ 建包起；可附 `enrichment.payment_terms` |
| 10 | `fulfillment.tech_confirm` | Skill 1 | 采购包技术确认（非变更） |
| 11 | `fulfillment.raise_po` | Skill 1 | Raise PO（非 Change PO） |
| 12 | `fulfillment.contract` | Skill 1 | 合同到达 |
| 13 | `fulfillment.payment_terms` | Skill 1 | 付款**条件**告知（写卡片，不是来请款） |
| 14 | `payment_claim.inbound` | Skill 2 | 供应商**来请款** → 步骤 1 已收到 |
| 14a | `payment_claim.qs_sent` | Skill 2 | 已发 QS 核对 |
| 14b | `payment_claim.qs_confirm` | Skill 2 | QS 确认金额 |
| 14c | `payment_claim.client_sent` | Skill 2 | 已发客户请款 |
| 14d | `payment_claim.client_approved` | Skill 2 | 客户批复（真正完成） |
| 15 | `unknown` | pending | 无法分类或置信不足 |

`change.*` 细则对齐 Skill 3 `references/email-stages.md`。业务编号与编排见 `skill-orchestration`。

### 防误伤

| 坑 | 规则 |
|----|------|
| 采购 FAQ「If this PR is a change order…original PO」 | **不是** Change PO；须显式 `change po` / `变更 PO` / `raise change order` |
| 履约「技术确认 / approved drawing」 | 无 COD/COT/PMI/变更序号锚点 → `fulfillment.tech_confirm` |
| 正文随口提 COD process | 无主题 COD、无 `COD`+序号、无 Change Order Document → 不判 `change.cod` |
| 裸 `Invoice` / 发票 | 无请款语境 → `unknown` |

## 付款条件 vs 请款申报

| | `fulfillment.payment_terms` | `payment_claim.inbound` |
|--|------------------------------|-------------------------|
| 人话 | 「以后按这些节点付」→ 写履约卡片 | 「我现在请这一笔」→ Skill 2 五步追踪；客户批复才算完成 |
| 路由 | Skill 1 | Skill 2 |

## enrichment（≠ 改路由）

| 标记 | 含义 | 谁消费 |
|------|------|--------|
| `payment_terms` | 正文含付款/请款节点 | Skill 1 写卡片付款节 |
| `has_quote_attachment` | 疑似报价附件 | Skill 1 抓金额 |
| `has_drawing` | 疑似图纸 | Skill 1/3 归档 |
| `schedule_attachment` | 疑似进度计划 | 编排表 B，非本 Skill 解析 |

## 置信度

| confidence | 动作 |
|------------|------|
| `high` | 可路由；**不等于判对了**（见下节） |
| `medium` | 可自动路由；缺包名/变更号时降级 |
| `low` | → `unknown` / pending，不得静默定稿 |

多采购包模糊、无包可挂、变更序号歧义 → pending（字段见 `io-contract.md`）。

## 线程回信怎么判

`classify_mail` 只扫主题+全文关键词，**不懂线程**：`Re:` / `回复:` 正文里常带着被引用的原邮件。原信里的 `RFP` / `COD` / `Raise PO` 会被当成「这封也是那一步」，并打出 `confidence: high`。

这不是偶发误伤，是分类器能力边界。**没有评测集前不要改 `classify_mail.py`**（会牵动 pull 邮箱自动分发）。判错由 **Agent 覆写 intent** 兜住，不另造一套分类器。

| 要 | 不要 |
|----|------|
| 只拿**最新一段回复**判断本封在办哪一步 | 被引用原文、页脚签名、FAQ 模板句带着跑 |
| 覆写后仍用本表的 `intent` 值，写入 route.json，并加 `"intent_verified": true` | 跟着错误 intent 再建一次采购包 / 再盖一次「RFP 发出」 |
| 吃不准 → pending 问人 | 因为 `high` 就直接 `dispatch` |

**履约常见错判**：顾问回 RFP 线程说「图纸没意见了 / approved / no further comment」→ 应是 `fulfillment.tech_confirm`（步骤 2），不是又一封 `fulfillment.rfp`。商务回「报价确认 / commercial confirmed」→ 仍走履约后续步骤，不是新 RFP。

**变更同样适用**：回信里引用了 COD/COT 原文，以最新一段是技术确认还是商务确认为准。
