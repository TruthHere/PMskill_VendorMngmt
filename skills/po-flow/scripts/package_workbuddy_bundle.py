#!/usr/bin/env python3
"""Pack Skill 1 + runtime siblings for WorkBuddy smoke tests.

Skills live under ``.cursor/skills/``. The project-foundation **library**
lives under ``.cursor/lib/`` (not a Skill). Zip still places it as a sibling
folder so scripts can find it next to the skills.

Excludes secrets, evals, tests, and local junk.
"""

from __future__ import annotations

import fnmatch
import zipfile
from datetime import datetime
from pathlib import Path

SKILL1 = Path(__file__).resolve().parents[1]
SKILLS_ROOT = SKILL1.parent
CURSOR_ROOT = SKILLS_ROOT.parent
LIB_ROOT = CURSOR_ROOT / "lib"
REPO = CURSOR_ROOT.parent
OUT_DIR = REPO / "dist" / "workbuddy"

# Minimum set for process_email → Tracker / card-data → vendor-card.
# new-project included so WorkBuddy can seed a project without Cursor.
RUNTIME_SKILLS = (
    "po-flow",
    "vendor-card",
    "mail-inbox",
    "critical-nodes",
    "mpp-to-excel",
    "read-pdf",
    "new-project",
    "payment-flow",
    "payment-sheet",
    "change-flow",
    "cashflow",
)
# skill-orchestration = 编排说明书（Rule 配套），不是 Skill
RUNTIME_LIBS = ("project-foundation", "skill-orchestration")

EXCLUDE_DIR_NAMES = {
    "__pycache__",
    "node_modules",
    "evals",
    "tests",
    ".git",
}
EXCLUDE_FILE_NAMES = {
    ".DS_Store",
    ".mailbox.secret",
    "mailbox-registry.json",
}
EXCLUDE_GLOBS = (
    "*.pyc",
    "*.secret",
    "*.pyo",
    "smoke_*.py",
    "run_all_evals.py",
)


def skip(rel: Path) -> bool:
    if any(p in EXCLUDE_DIR_NAMES for p in rel.parts):
        return True
    if rel.name in EXCLUDE_FILE_NAMES:
        return True
    return any(fnmatch.fnmatch(rel.name, g) for g in EXCLUDE_GLOBS)


INSTALL_MD = """# PM Skills 运行时包 · WorkBuddy / CodeBuddy 安装

打包时间：{stamp}
用途：在 WorkBuddy 上跑建项 / 履约 / 请款 / 变更等业务链路。

## 日常开发：这边改、那边测（推荐）

真源在仓库 `.cursor/skills/`（业务 Skill）和 `.cursor/lib/`（基建库 + 编排说明书）。改完后：

```bash
cd "/path/to/PMskills"
python3 scripts/sync_skills_to_workbuddy.py --with-openpyxl
```

然后**重启 WorkBuddy / 新开对话**再测。

## skills-root（重要）

解压后各文件夹的**上一级目录**就是 `skills-root`（常见 `~/.workbuddy/skills/`）。  
各 `SKILL.md` 里的命令写成：`python3 <skills-root>/<技能名>/scripts/….py` —— **不要**再写死 `.cursor/skills/...`。

## 为什么是一包多个文件夹？

脚本在 **skills 根下的邻居文件夹**里找依赖。`project-foundation`、`skill-orchestration` **不是业务 Skill**，但必须与各 Skill **并列**放置。

本包包含业务 Skill + 上述两个库。  
**未打入**：密钥、`evals/`、`smoke_*.py`、`run_all_evals.py`、tests。

## 安装

1. 解压本 zip。  
2. 把解压出的**各个文件夹**拷到 `~/.workbuddy/skills/`（或项目下 `.workbuddy/skills/` / `.codebuddy/skills/`）。  
3. 确认并列存在 `project-foundation/`、`skill-orchestration/` 与各业务 Skill。  
4. 重启 WorkBuddy / 新开对话。

## 编排规则（项目级，不是用户全局）

用 Skill 0 建项时，`init_project` 会自动写入：

`{{项目根}}/.codebuddy/rules/pm-skill-orchestration/RULE.mdc`

（内容来自 `skill-orchestration/ALWAYS.md`，`alwaysApply: true`。）  
**不会**写入 `~/.codebuddy/rules/`，避免串到无关对话。  
规则变更后请**新开对话**。可用「当前应用了哪些规则？」自检。

## 快速验收（对话）

> 请用 new-project 新建项目。先问齐：名称、编号、类型、地址、甲方、项目经理、文件夹放哪、币种、是否含税。不要问邮箱。
> 建完确认有「待处理邮件」文件夹，以及 `.codebuddy/rules/pm-skill-orchestration/RULE.mdc`。
> 之后把整封邮件放进「待处理邮件」，说「处理待处理邮件」。不要配置自动收信。

## 环境

- Python 3.10+  
- Tracker xlsx：`openpyxl`（见 `project-foundation/requirements.txt`）  
- 合同 OCR：见 `read-pdf` 文档  

## 和企微的关系（当前）

本包**不含**企微 API / 在线表格同步。先验证对话触发 → 本地落盘是否正确。
"""


def add_tree(zf: zipfile.ZipFile, skill_dir: Path, skill_name: str) -> int:
    n = 0
    for path in sorted(skill_dir.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(skill_dir)
        if skip(rel):
            continue
        arc = f"{skill_name}/{rel.as_posix()}"
        zf.write(path, arc)
        n += 1
    return n


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    zip_path = OUT_DIR / f"pm-skill1-workbuddy-runtime-{stamp}.zip"
    latest = OUT_DIR / "pm-skill1-workbuddy-runtime-latest.zip"
    install_path = OUT_DIR / "INSTALL-WorkBuddy.md"

    missing = [s for s in RUNTIME_SKILLS if not (SKILLS_ROOT / s / "SKILL.md").is_file()]
    if missing:
        raise SystemExit(f"Missing skills under {SKILLS_ROOT}: {missing}")
    missing_libs = [
        n
        for n in RUNTIME_LIBS
        if not (
            (LIB_ROOT / n / "scripts" / "common.py").is_file()
            or (LIB_ROOT / n / "README.md").is_file()
        )
    ]
    if missing_libs:
        raise SystemExit(f"Missing libs under {LIB_ROOT}: {missing_libs}")

    install_path.write_text(INSTALL_MD.format(stamp=stamp), encoding="utf-8")

    counts: dict[str, int] = {}
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("INSTALL-WorkBuddy.md", install_path.read_text(encoding="utf-8"))
        for name in RUNTIME_SKILLS:
            counts[name] = add_tree(zf, SKILLS_ROOT / name, name)
        for name in RUNTIME_LIBS:
            counts[name] = add_tree(zf, LIB_ROOT / name, name)

    # Stable alias for easy finding
    if latest.exists() or latest.is_symlink():
        latest.unlink()
    latest.write_bytes(zip_path.read_bytes())

    print(f"Wrote {zip_path}")
    print(f"Alias  {latest}")
    print(f"Install notes: {install_path}")
    for name, n in counts.items():
        print(f"  {name}: {n} files")
    print(f"Size: {zip_path.stat().st_size / 1024:.1f} KiB")


if __name__ == "__main__":
    main()
