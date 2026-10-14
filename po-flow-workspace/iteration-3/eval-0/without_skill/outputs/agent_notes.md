# agent_notes — misroute_init（without_skill）

## 结论

**未建采购包。** 主题含「项目初始化」，判定为阶段 0 邮件，应交给 Skill 0 / new-project；本目录阶段 0 已就绪，只做确认与路由标记。

## 邮件摘要

- 主题：`[项目初始化] Sample Project - SAMPLE`
- 正文：项目名称 Sample Project / 编号 SAMPLE / 类型 实验室
- 意图：`project_init`（非 RFP / Raise PO / 付款）

## 我做了什么

1. 解码 `init.eml`，核对与 `.skill/project.json`（Sample Project / SAMPLE / 实验室）一致。
2. 确认阶段 0 已存在：空 Tracker、`项目背景.md`、`项目档案/00_进度计划/`。
3. **未**新建采购包、**未**创建 `01_*` 文件夹、**未**改写 Tracker 数据行。
4. 写入 `process_result.json`：`reason=routed_to_skill0`，说明改用 Skill 0 / new-project。
5. 在 `.skill/pending.json` 留一条开放待办（同上原因）。
6. 写本说明与 `transcript.md`。

## 为什么

「项目初始化」是建项目根/档案/空 Tracker 的事；履约侧处理的是采购包生命周期。邮件已落到已初始化的项目根时，再硬建包会污染 Tracker。正确做法是识别误投并路由回 Skill 0。
