# transcript — eval-0 misroute-init（without_skill）

1. 列出工作目录：已有 `.skill/project.json`、空 Tracker、`项目背景.md`、`项目档案/00_进度计划/`（阶段 0 已 seed）。
2. 读取并 base64 解码 `_mail/init.eml`：主题 `[项目初始化] Sample Project - SAMPLE`；正文为项目名称/编号/类型。
3. 对照 `project.json`：邮件字段与现有档案一致 → 确认为初始化邮件，且项目已存在，无需重建。
4. 判定处理方式：不走 RFP/建包；结果记为 `intent=project_init`，`reason=routed_to_skill0`。
5. 写入/核对 `process_result.json`（note 指向 Skill 0 / new-project）；`.skill/pending.json` 留开放待办。
6. 检查：Tracker 无采购包数据行；无 `01_*` 包目录。
7. 写 `agent_notes.md`、本 `transcript.md`。
