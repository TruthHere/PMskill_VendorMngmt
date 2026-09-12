# 执行摘要 — eval-0 misroute-init（without_skill / run-1）

## 输入

- 工作目录：`.../eval-0/without_skill/outputs`（阶段 0 已就绪）
- 邮件：`_mail/init.eml`（主题含「项目初始化」，正文为 Sample Project / SAMPLE / 实验室）

## 处理结论

判定为**误投到履约侧的项目初始化邮件**。不建采购包、不建 `01_*` 目录、不改 Tracker。

结果写入：

- `process_result.json`：`reason=routed_to_skill0`，note 指向 Skill 0 / project-init
- `.skill/pending.json`：开放待办一条（同上原因）
- `agent_notes.md`：说明与理由

## 最终状态

项目仍为阶段 0 空壳：无采购包行、无履约卡片、进度计划目录为空。初始化邮件已识别并标记应转交 Skill 0。
