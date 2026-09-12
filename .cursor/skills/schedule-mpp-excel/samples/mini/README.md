# mini 样例

源文件：`project_schedule.csv`（模拟从 Project 导出的扁平表）。

## 本地跑通

```bash
python3 .cursor/skills/schedule-mpp-excel/scripts/convert_schedule.py \
  --source .cursor/skills/schedule-mpp-excel/samples/mini/project_schedule.csv \
  --out-dir .cursor/skills/schedule-mpp-excel/samples/mini/out \
  --project-name "Mini Demo"
```

预期产物：

- `project_schedule_project_view.xlsx` — 左表 + 右甘特（月带）+「图例」
- `project_schedule_schedule.csv` — 机读
- `project_schedule_schedule_structured.xlsx` — 机读扁平表

## 读 .mpp 前（一次）

```bash
python3 .cursor/skills/schedule-mpp-excel/scripts/setup_mppjs.py
```

之后直转 MPP，无需每次 `npx`、无需先导出 XML。

## SARL 回归（视觉金标）

```bash
python3 .cursor/skills/schedule-mpp-excel/scripts/convert_schedule.py \
  --source "$HOME/Desktop/Test/SARL Ph1 Refresh Project - Master Schedule 260519.mpp" \
  --out-dir "$HOME/Desktop/Test" \
  --stem "SARL_Ph1_Refresh_Master_Schedule_260519" \
  --project-name "SARL Ph1 Refresh"
```

验收：打开 `*_project_view.xlsx` — 有月份带、甘特无满屏细格、WBS 列、前置含滞后（如有）、关键条为红、含「图例」页。勿把 `*_project_view.xlsx` 再当 `--source`。
