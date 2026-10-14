# Agent Notes — eval-1 without_skill（RFP 转发 → 建包）

## 做了什么

1. 读取 `_mail/rfp.eml`，解析出采购包 **BMS**、供应商 **BOSCH Building Technologies**、对接邮箱 `procurement@bosch-build.example.com`、类型 **纯供应**。
2. 在工作目录创建采购包文件夹 `01_BMS_BOSCH/`，含标准子目录 `01_合同报价`～`07_往来文件`。
3. 将 RFP 原邮件归档至 `01_BMS_BOSCH/07_往来文件/BMS_邮件_20260801_v1_RFP邮件.eml`。
4. 写入 `card-data.json`（供应商名等字段已填；付款节点仍为空，因 RFP 阶段尚无金额/付款条件）。
5. 生成 `履约条件卡片.html`、`请款申请.html`（卡片含「发起请款」链接）。
6. 更新 Tracker CSV：唯一一行 BMS；里程碑「RFP 发出」= `2026-08-01`；卡片/文件夹路径指向本包。

## 为什么

阶段 0 项目已就绪，本任务是 RFP 转发建包：落盘采购包目录、归档往来邮件、登记 Tracker 并发出 RFP 状态、准备履约卡片骨架，便于后续技术方案确认 / Raise PO / 请款。

## 约束说明

本 run 为 **without_skill** baseline：未调用 `po-flow` 及相关脚本，仅用普通文件操作与推理完成。
