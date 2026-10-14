# 执行摘要 · eval-0 / with_skill / run-1（misroute_init）

## 任务
处理「项目初始化」邮件 `_mail/init.eml`，工作目录阶段 0 已就绪。

## 判定（Skill 1）
按 `po-flow`：阶段 0 / `[项目初始化]` **不归 Skill 1**（从建包起）；应分发到 **Skill 0 `new-project`**。编排见 `skill-orchestration`：`project_init` → Skill 0。

## 执行
1. 识别主题 `[项目初始化] Sample Project - SAMPLE`，正文：项目名称/编号/类型。
2. 跑 `process_email.py`（intent=`project_init`）→ `reason=routed_to_skill0`，stdout → `outputs/process_result.json`；写入 pending，**未建采购包**。
3. 交接 Skill 0：`handle_init_email.py` → 已有 `project.json`，`auto=true` / `confirm_existing_project`（无需再 init）。

## 结果
- Tracker 仍为空，无 `01_*` 包目录。
- 项目档案保持阶段 0 就绪；后续可转发 RFP 走真正的 Skill 1 建包。
