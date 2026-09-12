# Agent Notes — eval-2 without_skill（Raise PO → 付款指示）

## 做了什么

1. **Raise PO 邮件**（`_mail/raise_po.eml`）  
   - 解析：采购包 BMS / BOSCH Building Technologies；含税金额 ¥1,280,000；交期 2026-09-30；对接邮箱 `procurement@bosch-build.example.com`。  
   - 归档至 `01_BMS_BOSCH/07_往来文件/BMS_邮件_20260801_v1_RaisePO.eml`。  
   - Tracker：填写 **金额含税** `1280000.00`、**交期摘要** `2026-09-30`、**PO 已发起** `2026-08-01`；同步 xlsx。  
   - 卡片 `card-data.json`：写入 `total_amount`、`delivery_schedule`。

2. **付款指示邮件**（`_mail/payment.eml`）  
   - 解析三节点：预付款 30%（PO 签发后 7 日内）/ 到货验收 60%（全部到货并验收合格后）/ 尾款 10%（质保期满无质量问题后）。  
   - 归档至 `01_BMS_BOSCH/07_往来文件/BMS_邮件_20260801_v1_付款指示.eml`。  
   - 写入卡片 `payment_nodes`（含条件、来源、请款附件提示；到货节点挂交期里程碑）。  
   - Tracker **下一付款节点** = `预付款 / Advance 30%`。  
   - 生成/更新 `履约条件卡片.html`、`请款申请.html`。

3. 杂项：更新 `.skill/project.json` 的 `tracker_last_updated`；邮件副本落入 `.skill/inbox`。

## 为什么

包已存在且技术方案已确认，本任务是 PO 下发 + 付款条件落地：Tracker 标 PO、卡片落金额与三段付款，方便后续请款。

## 约束说明

本 run 为 **without_skill** baseline：未阅读 / 未调用 `contract-fulfillment-struct` 或 fulfillment-card Skill，仅用邮件解析与文件更新完成。
