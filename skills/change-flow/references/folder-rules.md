# 变更归档路径与命名

复用 Skill 1 包目录；本 Skill **不**创建项目根。

## 相关路径

```text
{project_root}/
├── {项目名}_Status Tracker.xlsx          ← 只读（给人看）
├── {项目名}_Change Log.xlsx              ← 本 Skill 同步写出
├── .skill/
│   ├── status_tracker.csv                ← Tracker 机读（只读）
│   └── change_log.csv                    ← 本 Skill 写（真源）
└── {序号}_{采购包}_{供应商}/
    ├── 02_图纸/          ← 变更图纸同步
    ├── 04_变更洽商/      ← 变更主归档
    ├── 07_往来文件/      ← .eml 往来
    └── card-data.json
```

## 原则

1. 变更相关邮件：**整封 `.eml` 进 07 + 04**（允许双份）。
2. 业务附件（报价、终版意见等）→ `04_变更洽商/`。
3. 技术图纸 / 送审图 → `04` **与** `02` 各一份。
4. 禁止签名动图当变更附件。

## 命名

阶段简写：`COD` / `PMI` / `TECH` / `TC` / `QUOTE` / `CP` / `CHPO`。  
脚本实际用 `archive_file`：`{包}_{类型}_{日期}_{阶段}_{变更序号}{ext}`。

Change Log「归档路径」写相对根目录，优先 `…/04_变更洽商/`。

## 包对不上

pending（`package_unmatched`），勿落到错误包。
