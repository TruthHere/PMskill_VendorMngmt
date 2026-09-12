# 文件夹结构与归档规则

## 项目根目录（阶段 0 创建）

**PM 日常只看两样**：`{项目名称}_procurement_packages_status_tracker.csv` + `项目背景.md`。

```
{项目根路径}/
├── Test project 1_procurement_packages_status_tracker.csv   # 采购包状态总览
├── Test project 1_change_log.csv                            # 变更 Change Log（change-archive）
├── Test project 1_项目通讯录.xlsx                            # 供应商对接人（project-directory）
├── 项目背景.md                                            # 人类可读项目信息 + Tracker 最后更新
├── .skill/                                                # Skill 内部（Finder 默认隐藏，类似 .git）
│   ├── project.json
│   ├── pending.json                                       # 待确认：每条必须带 skill，只能由该 Skill 关闭
│   ├── schedule.json                                      # 进度 pending 在这里，不进 pending.json
│   ├── critical_nodes_timeline.html                     # 与进度区同款时间线（机读旁路）
│   ├── mailbox_state.json
│   └── inbox/
├── 项目档案/
│   └── 00_进度计划/
│       └── 关键节点时间线.html                           # 采购包录入时由 schedule-critical-nodes 同步生成
├── 01_{采购包名称}_{供应商简称}/
│   └── 关键节点时间线.html                               # 该包过滤视图（建包时同步）
└── …
```

### 为什么不用下划线前缀？

早期用 `_系统/`、`_项目档案/` 是为了在 Finder 里把目录顶到列表最前、标记「非日常文件」。这不够直观，现已改为：

| 旧名 | 新名 | 说明 |
|------|------|------|
| `_系统/` | `.skill/` | 点开头 = macOS 默认隐藏，根目录更干净 |
| `_项目档案/` | `项目档案/` | 正常中文名，无下划线 |
| `tracker.csv` | `{项目名}_procurement_packages_status_tracker.csv` | 见名知意 |

### Tracker 文件命名

```
{项目名称}_procurement_packages_status_tracker.csv
```

示例：`Test project 1_procurement_packages_status_tracker.csv`

- 文件名含**项目名** + 固定后缀 `procurement_packages_status_tracker`
- 文件**第一行**写入最后更新时间（Excel 打开时 A1 可见）：
  ```
  # 最后更新,2026-07-19T20:30:00+08:00
  采购包名称,供应商名称,…
  ```
- `项目背景.md` 与 `.skill/project.json` 同步记录 `tracker_last_updated`

## 采购包文件夹（步骤 1 创建）

命名：`{序号}_{采购包名称}_{供应商简称}/`

```
01_BMS_dismantling_BOSCH/
├── 01_合同报价/
├── 02_图纸/
…
```

## 旧项目迁移

```bash
python3 .cursor/lib/project-foundation/scripts/migrate_project_layout.py \
  --project-root "/path/to/project"
```

兼容读取：`.skill/` 与 `_系统/`、`项目档案/` 与 `_项目档案/`、`tracker.csv` 与新版 Tracker 文件名均可识别。

## 其余规则

文件命名、步骤归档、附件过滤等同前版；详见 archive_file.py 与各步骤 SOP。
