# 输入格式与依赖

## 推荐优先级（先认格式，不是默认 MPP）

收到附件时**先判断类型**，再选路径：

1. **已是机读 `.csv` / 扁平 `.xlsx`**（第 1 行任务表头）— 可直接给 critical-nodes，或经本 Skill 再出人看版甘特  
2. **`.mpp`** — 本 Skill 直读（依赖 mppjs；首次 `setup_mppjs.py`）  
3. **Project XML（`.xml`）** — 已有 XML 时方便  
4. **人看版 `*_project_view.xlsx`** — **不是源**；找 `*_schedule.csv` 或回到原始 mpp/任务表

## 跨系统兼容（Windows / Linux / Mac）

写 Excel、读 CSV/XML 的部分是 **纯 Python**，Mac / Windows / Linux 都能用。

卡点只在「直读 `.mpp`」：要靠 **当前电脑对应的** mppjs 原生程序，**不能**把苹果电脑上装好的文件拷到 Windows/Linux 用。

| 系统 | 直读 `.mpp`（mppjs） | 说明 |
|------|----------------------|------|
| Mac（Apple Silicon，M 系列） | ✅ | `darwin-arm64` |
| Mac（Intel） | ❌ 无官方包 | 用 Project 另存 XML，或装 Java 17+ + `pip install mpxj` |
| Windows（普通 x64） | ✅ | `win32-x64`；本机跑 setup |
| Windows（ARM） | ❌ 无官方包 | 同上：XML 或 Java+mpxj |
| Linux x64 / ARM64 | ✅ | `linux-x64` / `linux-arm64` |

### 换电脑时怎么做（必做）

在**那台要转 MPP 的电脑**上：

1. 安装 **Node.js ≥ 20**（带 npm）
2. 跑一次：

```bash
python3 .cursor/skills/mpp-to-excel/scripts/setup_mppjs.py
```

3. 用一份小 `.mpp` 试转；几秒内出 CSV 即正常。

**不要**提交或拷贝 `scripts/vendor/`、`scripts/.mppjs/`（已在 `.gitignore`）。这两处是本机专用；跨系统共用会装错二进制。

## `.mpp` 怎么工作

脚本会把 `.mpp` 转成临时 MSPDI XML 再解析，优先顺序：

1. 环境变量 `MPPJS_BINARY`（指向 `mpxj-convert`）
2. `scripts/.mppjs/.../mppjs-<本机平台>/bin/mpxj-convert`（**优先匹配当前系统**）
3. `scripts/vendor/mpxj-convert`（本机旁路；勿跨系统拷贝）
4. PATH 上的 `mpxj-convert`
5. 自动 `npm install @byteink/mppjs` 到 `scripts/.mppjs/`（**首次一次**，可能较慢）
6. 最后才 `npx`（超时默认 **600** 秒，可用 `MPPJS_TIMEOUT` 调整）

### 首次准备（推荐跑一次）

```bash
python3 .cursor/skills/mpp-to-excel/scripts/setup_mppjs.py
```

之后转 MPP 应在数秒内完成，不再依赖每次 `npx` 下载。

### 备选：Java + mpxj

平台没有官方 mppjs 包，或 Node 装不上时：

```bash
pip3 install mpxj openpyxl
# 且 java 17+ 在 PATH
```

或在 Microsoft Project 里把计划另存为 XML，再喂本 Skill。

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
