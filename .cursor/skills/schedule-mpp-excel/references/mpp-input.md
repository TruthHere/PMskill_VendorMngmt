# 输入格式与依赖

## 推荐优先级

1. **`.mpp`** — 本 Skill 主路径：直读 MPP（依赖 mppjs 原生二进制，**无需 Java、无需先导出 XML**）
2. **`.xlsx` / `.csv`** — 已有任务表
3. **Project XML（`.xml`）** — 可选；仅在你已经有 XML 时方便，不是使用本 Skill 的前提

## `.mpp` 怎么工作

脚本会把 `.mpp` 转成临时 MSPDI XML 再解析，优先顺序：

1. 环境变量 `MPPJS_BINARY`（指向 `mpxj-convert`）
2. `scripts/vendor/mpxj-convert`（可提交旁路或由 setup 复制）
3. `scripts/.mppjs/node_modules/@byteink/mppjs-*/bin/mpxj-convert`（本地 npm 安装）
4. PATH 上的 `mpxj-convert`
5. 自动 `npm install @byteink/mppjs` 到 `scripts/.mppjs/`（**首次一次**，可能较慢）
6. 最后才 `npx`（超时默认 **600** 秒，可用 `MPPJS_TIMEOUT` 调整）

### 首次准备（推荐跑一次）

```bash
python3 .cursor/skills/schedule-mpp-excel/scripts/setup_mppjs.py
```

之后转 MPP 应在数秒内完成，不再依赖每次 `npx` 下载。

### 备选：Java + mpxj

```bash
pip3 install mpxj openpyxl
# 且 java 17+ 在 PATH
```

## Project XML（MSPDI）

- 纯 Python 解析
- 读取：UID / ID / Name / WBS / OutlineLevel / Start / Finish / Duration / PercentComplete / Milestone / Summary / Critical / PredecessorLink（含 Type、LinkLag）
- LinkLag 单位为「十分之一分钟」；按 8h 工作日换算为滞后天数，输出如 `5FS+3d`

## 表格输入（xlsx/csv）列别名

识别常见中英表头（任务名称 / 开始 / 结束 / 采购包等），并扩展 Project 常用列（含 `WBS`、工期、前置任务）。详细别名见脚本 `readers.py`。

**禁止**把本 Skill 产出的人看版 `*_project_view.xlsx` 再当输入：表头不在第 1 行，且甘特色块是静态填充。脚本会拒读并提示改用 `*_schedule.csv` / `*_schedule_structured.xlsx` 或原始 `.mpp`。

人看版里改开始/结束**不会**自动更新甘特；需要更新时重新运行 `convert_schedule.py`。

## 输出落盘约定

源 `Foo.mpp` →

- `Foo_project_view.xlsx`（给人看；勿回读）
- `Foo_schedule.csv`（机读）
- `Foo_schedule_structured.xlsx`（机读；可用 `--no-structured-xlsx` 关闭）
