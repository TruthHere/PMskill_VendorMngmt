---
name: schedule-mpp-excel
description: >-
  将 Microsoft Project（.mpp / Project XML）或粗表进度转为「左侧任务表 + 右侧甘特」的
  Project 风格 Excel，并同步导出机器可读 CSV/xlsx（前四列：任务名称、开始日期、结束日期、采购包）。
  务必在用户提到 MPP、Microsoft Project、Project 甘特搬到 Excel、进度计划可视化 Excel、
  mpp 转 csv/xlsx、Project 样式 Excel、甘特色块表时使用。
---

# Schedule MPP → Project 风格 Excel

先确认输入是 MPP / XML / 粗表再转换；结构不清则说明限制，不瞎填日期列。

## 权威文档

- `references/mpp-input.md` — 输入格式、依赖（mppjs / Java 备选）、降级路径
- `references/project-view-layout.md` — 左侧列 + 右侧甘特（月带/周标）版式
- `references/structured-export.md` — 机器可读 CSV/xlsx 契约

## 能力边界

| 做 | 不做 |
|----|------|
| 读 `.mpp`（推荐 Node+mppjs；或 Java+mpxj）、Project XML、xlsx/csv | 不推断关键节点、不写付款区间 |
| 输出 **Project 视图 xlsx**（左任务表 + 右甘特） | 不替代 MS Project 编辑/资源平衡 |
| 输出 **结构化 CSV**（及可选结构化 xlsx） | 不做依赖箭线 / 进度条叠加 / HTML 报告 |

**定位**：进度计划的「人看版 + 机读版」转换工具。交付 Excel/CSV 即止。

## 输入

| 格式 | 说明 |
|------|------|
| `.mpp` | **主路径**；首次请跑 `scripts/setup_mppjs.py`（之后本地二进制直转，无需 XML） |
| `.xml` | MS Project「另存为 XML」 |
| `.xlsx` / `.csv` | 已有任务表；至少含名称 + 开始/结束。**不要**把本 Skill 的 `*_project_view.xlsx` 当输入 |

有项目目录时可归档到 `项目档案/00_进度计划/`；也可写到 `--out-dir` 任意路径。

## 输出（默认写到同一目录）

| 文件 | 用途 |
|------|------|
| `{stem}_project_view.xlsx` | 给人看：左 Project 列 + 右甘特（月带）+「图例」页 |
| `{stem}_schedule.csv` | 机读扁平表（表头见 `structured-export.md`） |
| `{stem}_schedule_structured.xlsx` | 可选；同数据的扁平表（无甘特） |

## 工作流（必须遵守）

1. 确认源文件（`.mpp` / `.xml` / `.xlsx` / `.csv`）与输出目录
2. 阅读 `references/mpp-input.md`（若读 `.mpp`）与 `project-view-layout.md`
3. 运行转换脚本（见下）
4. 向用户汇报：任务行数、甘特起止日、输出路径
5. **完成**。人看版改日期不会更新甘特；需更新时重新跑本脚本。

### 标准命令

```bash
python3 .cursor/skills/schedule-mpp-excel/scripts/convert_schedule.py \
  --source "/path/to/project.mpp" \
  --out-dir "/path/to/out"
```

常用可选参数：

```bash
  --gantt-unit week          # day | week（默认 week；跨度>4个月强制 week）
  --no-structured-xlsx       # 不写 *_schedule_structured.xlsx
  --project-name "某某项目"   # 写入表头元数据
```

无 `--out-dir` 时：写到源文件同目录。读 `.mpp`：先 `python3 .../scripts/setup_mppjs.py`（一次），详见 `mpp-input.md`。

## 样例

- `samples/mini/` — 小型 CSV 源 + 预期说明
- SARL 回归：见 `samples/mini/README.md`
