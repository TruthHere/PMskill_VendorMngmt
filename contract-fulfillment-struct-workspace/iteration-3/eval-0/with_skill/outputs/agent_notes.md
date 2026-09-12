# agent_notes · misroute_init

## 结论
**未建采购包。** 识别为项目初始化邮件，按 Skill 1 边界 **重定向到 Skill 0（project-init）**。

## 做了什么
1. 读 `contract-fulfillment-struct` Skill：阶段 0 / `[项目初始化]` 不归本 Skill。
2. 对 `_mail/init.eml` 跑 `process_email.py` → `reason=routed_to_skill0`，写入 `pending`，**不**走 RFP 建包。
3. 按指引调用 Skill 0 `handle_init_email.py`：工作目录已有 `.skill/project.json`，结果 `confirm_existing_project`（档案已就绪，无需再 init）。

## 当前状态
- 项目：Sample Project / SAMPLE（阶段 0 已完成）
- Tracker：空表，无采购包行
- 无 `01_*` 采购包目录
- 后续可开始转发 RFP（真正的 Skill 1 建包）
