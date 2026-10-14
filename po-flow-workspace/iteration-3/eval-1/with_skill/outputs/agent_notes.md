# agent_notes · rfp-forward（with_skill）

## 结论
已按 Skill 1 初始化采购包 **BMS**（供应商 BOSCH Building Technologies，纯供应）。Tracker 写入里程碑「RFP 发出」；履约卡片与请款页经 vendor-card 渲染。

## 做了什么
1. 确认阶段 0：`.skill/project.json` 已存在（Sample Project / SAMPLE）。
2. 读 `po-flow` Skill，对 `_mail/rfp.eml` 跑 `process_email.py`（stdout → `process_result.json`）。
3. 建包成功：`01_BMS_BOSCH/`、Tracker 一行、`.eml` 归档至 `07_往来文件/`、`card-data.json` + `履约条件卡片.html` + `请款申请.html`。
4. 无进度源：`schedule.json` 为空，时间线同步软跳过（不阻断建包）。

## 当前状态
| 项 | 结果 |
|----|------|
| 包目录 | `01_BMS_BOSCH/`（01~07 子目录齐全） |
| Tracker | 1 行：BMS / BOSCH / 供应；`RFP 发出=2026-08-01` |
| 对接人 | `procurement@bosch-build.example.com` |
| 往来 | `07_往来文件/*.eml` 已归档 |
| 卡片 | `履约条件卡片.html` + `请款申请.html` + `card-data.json` |
| 金额/付款节点 | RFP 邮件未提供 → 卡片 quality 提醒（待后续报价/合同补全） |
| pending | 空 |

## 待确认（测试期清单）
```
【Skill1 · 待确认】项目 SAMPLE · 步骤1 · RFP
1. 采购包名称：BMS
2. 供应商：BOSCH Building Technologies
3. 对接人邮箱：procurement@bosch-build.example.com
4. 采购包类型：供应（纯供应）
5. 归档：07_往来文件（附件无图纸）
回复：全部确认 / 修正项 / 取消
```
