---
name: mpp-to-excel
description: >-
  进度计划格式识别与转换：把 .mpp / Project XML / 粗表 xlsx/csv 转成机读
  *_schedule.csv（及可选结构化 xlsx），并可选产出「左侧任务表 + 右侧甘特」的
  Project 风格 Excel（*_project_view.xlsx）。不是「只处理 MPP」。
  务必在用户提到进度计划转换、认 schedule 格式、MPP、Microsoft Project、
  Project 甘特搬到 Excel、mpp/xlsx 转 csv、Project 样式 Excel、甘特色块表时使用。
---

# Schedule → 机读 CSV（+ 可选 Project 风格 Excel）

**先认输入格式，再转换。** 本 Skill 是进度的「规范化入口」，不是默认「来的一定是 MPP」。

先确认输入是 MPP / XML / 粗表再转换；结构不清则说明限制，不瞎填日期列。

## 编排硬规则（摘要）

跨 Skill / 进度 / 合同 PDF / 邮件分发 → 先读 `<skills-root>/skill-orchestration/ALWAYS.md`（细节见同目录 `README.md`）。
单独使用功能 Skill 时禁止擅自串联履约/请款；脚本已串完的不要双跑；时间线对人只有 `项目档案/00_进度计划/关键节点时间线.html` 一份。
`skills-root` = 本机 Skills 安装根（WorkBuddy 常见 `~/.workbuddy/skills/`）。命令写成 `python3 <skills-root>/<技能名>/scripts/…`。

## 权威文档

- `references/mpp-input.md` — 输入格式、依赖（mppjs / Java 备选）、**跨系统（Win/Linux/Mac）**、降级路径
- `references/project-view-layout.md` — 左侧列 + 右侧甘特（月带/周标）版式
- `references/structured-export.md` — 机器可读 CSV/xlsx 契约

## 能力边界

| 做 | 不做 |
|----|------|
| 读 `.mpp`（推荐 Node+mppjs；或 Java+mpxj）、Project XML、xlsx/csv | 不推断关键节点、不写付款区间 |
| 输出 **Project 视图 xlsx**（左任务表 + 右甘特） | 不替代 MS Project 编辑/资源平衡 |
| 输出 **结构化 CSV**（及可选结构化 xlsx） | 不做依赖箭线 / 进度条叠加 / HTML 报告 |

## 输入（按识别结果处理）

| 认出来的格式 | 怎么做 |
|------|------|
| `.mpp` | 主路径之一；首次跑 `scripts/setup_mppjs.py` |
| `.xml` | MS Project「另存为 XML」 |
| 扁平 `.xlsx` / `.csv`（第 1 行是任务表头） | 直接转换 → 机读 CSV + 可选人看版甘特 |
| **人看版** `*_project_view.xlsx` | **拒绝当输入**（假源）。改用同目录 `*_schedule.csv` / `*_schedule_structured.xlsx`，或原始 `.mpp` / 任务表 |

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
python3 <skills-root>/mpp-to-excel/scripts/convert_schedule.py \
  --source "/path/to/project.mpp" \
  --out-dir "/path/to/out"
```

常用可选参数：

```bash
  --gantt-unit week          # day | week（默认 week；跨度>4个月强制 week）
  --no-structured-xlsx       # 不写 *_schedule_structured.xlsx
  --project-name "某某项目"   # 写入表头元数据
```

无 `--out-dir` 时：写到源文件同目录。读 `.mpp`：在**当前电脑**先跑一次 `setup_mppjs.py`（换 Win/Linux 也要本机重跑，勿拷 Mac 的 vendor）。详见 `mpp-input.md`。

## 样例

- `samples/mini/` — 小型 CSV 源 + 预期说明
- SARL 回归：见 `samples/mini/README.md`
