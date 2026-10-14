# 文件夹结构与归档规则

## 项目根目录（阶段 0 创建）

**PM 日常只看根目录的英文 Excel**（不要和机读 CSV 混放）：

```
{项目根路径}/
├── Test project 1_Status Tracker.xlsx      # 采购包状态总览（给人看）
├── Test project 1_Change Log.xlsx          # 变更台账（给人看）
├── Test project 1_Cash Flow Forecast.xlsx  # 现金流预测（按需生成）
├── 项目背景.md
├── 待处理邮件/                              # 人另存的整封 .eml，说「处理待处理邮件」后才读
├── .skill/                                 # 机读文件（Finder 默认隐藏）
│   ├── project.json
│   ├── status_tracker.csv                  # Tracker 真源（脚本读写）
│   ├── change_log.csv                      # Change Log 真源（Skill 3 写）
│   ├── pending.json
│   ├── schedule.json
│   ├── cashflow_forecast.json
│   ├── mailbox_state.json
│   └── inbox/
├── 项目档案/
│   └── 00_进度计划/
├── 01_{采购包名称}_{供应商简称}/
└── …
```

### 命名（英文后缀）

| 给人看（项目根） | 机读（`.skill/`） |
|------------------|-------------------|
| `{项目名}_Status Tracker.xlsx` | `status_tracker.csv` |
| `{项目名}_Change Log.xlsx` | `change_log.csv` |
| `{项目名}_Cash Flow Forecast.xlsx` | `cashflow_forecast.json` |

旧版根目录 `*_procurement_packages_status_tracker.csv` / `*_change_log.csv` / `*_现金流预测.xlsx` 仍可被识别；下次保存会迁到新布局。

### 为什么不用下划线前缀？

早期用 `_系统/`、`_项目档案/`；现已改为 `.skill/`（隐藏）与 `项目档案/`。

## 采购包文件夹（步骤 1 创建）

命名：`{序号}_{采购包名称}_{供应商简称}/`

```
01_BMS_dismantling_BOSCH/
├── 01_合同报价/
├── 02_图纸/
├── 03_请款记录/
├── 04_变更洽商/
…
```

## 旧项目迁移

```bash
python3 .cursor/lib/project-foundation/scripts/migrate_project_layout.py \
  --project-root "/path/to/project"
```

兼容读取：旧 CSV 名、旧中文 Excel 名均可识别。

## 图纸归档（`02_图纸/`）

| 来件 | 怎么放 |
|------|--------|
| dwg / pdf / zip 等图纸附件 | 按 `archive_file` 命名拷进本目录 |
| 邮件签名、`image001.png` 这类 inline 图 | 不归档 |
| 图纸只在云盘链接（Box / SharePoint 等），没有可存附件 | **必须留指针**：`{包}_图纸链接_{日期}_v1_云盘指针.md`，写上 URL、密码（如有）、来源邮件主题。不要留空文件夹让人以为没收到图纸 |
| 不要默认登录云盘把文件拉下来 | 用户明确要求再下载 |

## 其余规则

文件命名、步骤归档、附件过滤详见 archive_file.py 与各步骤 SOP。
