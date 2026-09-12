#!/usr/bin/env python3
"""Apply Master Schedule nodes (from PM) onto Desktop test project cards."""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

from archive_file import archive_file  # noqa: E402
from common import (  # noqa: E402
    PROJECT_JSON,
    SCHEDULE_JSON,
    load_json,
    load_tracker_packages,
    now_iso,
    project_archive_dir,
    save_json,
    system_dir,
)
_SKILLS_ROOT = SCRIPTS.parent.parent
_FC_SCRIPTS = _SKILLS_ROOT / "fulfillment-card" / "scripts"
if str(_FC_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_FC_SCRIPTS))
from render_card import patch_and_render  # noqa: E402

PROJECT = Path("/Users/truth_here/Desktop/Test Project 1 - Procurement")
MPP = Path(
    "/Users/truth_here/Desktop/Test/SARL Ph1 Refresh Project - Master Schedule 260519.mpp"
)

# Dates are provisional (mail cues). MPP archive is source of truth for structure;
# exact MPP dates need Java/mpxj later.
MILESTONES = [
    {"name": "开工", "date": "2026-07-01"},
    {"name": "移交 Handover", "date": "2027-03-31"},
    {"name": "BMS 到货", "date": "2026-09-30", "package": "BMS"},
    {
        "name": "BMS 安装",
        "date": "2026-11-15",
        "end_date": "2026-11-30",
        "package": "BMS",
    },
    {"name": "BMS 最终验收", "date": "2027-03-31", "package": "BMS"},
    {"name": "Glazing-partition 到货", "date": "2026-07-15", "package": "Glazing-partition"},
    {
        "name": "Glazing-partition 安装",
        "date": "2026-08-15",
        "end_date": "2026-08-31",
        "package": "Glazing-partition",
    },
    {"name": "Glazing-partition 验收", "date": "2026-09-30", "package": "Glazing-partition"},
    {
        "name": "Power-Distribution-Box 到货",
        "date": "2026-07-15",
        "package": "Power-Distribution-Box",
    },
    {
        "name": "Power-Distribution-Box 安装",
        "date": "2026-08-31",
        "package": "Power-Distribution-Box",
    },
    {"name": "EPMS 验收", "date": "2026-11-30", "package": "EPMS"},
    {"name": "IT-cabling 到货", "date": "2026-07-31", "package": "IT-cabling"},
    {
        "name": "IT-cabling 安装",
        "date": "2026-08-01",
        "end_date": "2027-02-28",
        "package": "IT-cabling",
    },
    {"name": "IT-cabling 验收", "date": "2027-03-31", "package": "IT-cabling"},
    {
        "name": "Initial-cleaning 服务完成",
        "date": "2026-08-31",
        "package": "Initial-cleaning",
    },
]

PAYMENT_BY_PACKAGE = {
    "BMS": [
        {
            "name": "到货 / Delivery",
            "pct": "",
            "condition": "设备到货",
            "source": "PM 指定节点 / Master Schedule",
        },
        {
            "name": "安装 / Installation",
            "pct": "",
            "condition": "安装完成",
            "source": "PM 指定节点 / Master Schedule",
        },
        {
            "name": "最终验收 / Final acceptance",
            "pct": "",
            "condition": "最终验收",
            "source": "PM 指定节点 / Master Schedule",
        },
    ],
    "Glazing-partition": [
        {
            "name": "到货 / Delivery",
            "pct": "",
            "condition": "材料到货",
            "source": "PM 指定节点 / Master Schedule",
        },
        {
            "name": "安装 / Installation",
            "pct": "",
            "condition": "安装完成",
            "source": "PM 指定节点 / Master Schedule",
        },
        {
            "name": "验收 / Acceptance",
            "pct": "",
            "condition": "验收",
            "source": "PM 指定节点 / Master Schedule",
        },
    ],
    "Power-Distribution-Box": [
        {
            "name": "到货 / Delivery",
            "pct": "",
            "condition": "到货",
            "source": "PM 指定节点 / Master Schedule",
        },
        {
            "name": "安装 / Installation",
            "pct": "",
            "condition": "安装完成",
            "source": "PM 指定节点 / Master Schedule",
        },
    ],
    "EPMS": [
        {
            "name": "验收 / Acceptance",
            "pct": "",
            "condition": "验收",
            "source": "PM 指定节点 / Master Schedule",
        },
    ],
    "IT-cabling": [
        {
            "name": "到货 / Delivery",
            "pct": "",
            "condition": "材料到货",
            "source": "PM 指定节点 / Master Schedule",
        },
        {
            "name": "安装 / Installation",
            "pct": "",
            "condition": "安装完成",
            "source": "PM 指定节点 / Master Schedule",
        },
        {
            "name": "验收 / Acceptance",
            "pct": "",
            "condition": "验收",
            "source": "PM 指定节点 / Master Schedule",
        },
    ],
    "Initial-cleaning": [
        {
            "name": "服务完成 / Service completion",
            "pct": "",
            "condition": "服务完成",
            "source": "PM 指定节点 / Master Schedule",
        },
    ],
}

# Aliases from earlier duplicate inject
PAYMENT_BY_PACKAGE["GlazingpartitionJEB"] = PAYMENT_BY_PACKAGE["Glazing-partition"]
PAYMENT_BY_PACKAGE["Power-distribution-box"] = PAYMENT_BY_PACKAGE["Power-Distribution-Box"]
PAYMENT_BY_PACKAGE["Initial-Cleaning"] = PAYMENT_BY_PACKAGE["Initial-cleaning"]


def main() -> None:
    dest = archive_file(
        source=MPP,
        dest_dir=project_archive_dir(PROJECT, create=True) / "00_进度计划",
        package_name="项目级",
        file_type="进度计划",
        description="总进度MPP",
        version="v260519",
    )
    print("archived:", dest)

    schedule = {
        "milestones": MILESTONES,
        "source_mpp": str(dest),
        "imported_at": now_iso(),
        "note": (
            "节点结构按 PM 指定；日期为暂定（邮件交期线索）。"
            "本机无 Java，未能从 .mpp 解析精确日期。"
        ),
    }
    save_json(system_dir(PROJECT) / SCHEDULE_JSON, schedule)

    csv_path = (
        project_archive_dir(PROJECT) / "00_进度计划" / "project_schedule_from_mpp_nodes.csv"
    )
    lines = ["里程碑,开始日期,结束日期,采购包"]
    for item in MILESTONES:
        pkg = item.get("package", "")
        lines.append(
            f"{item['name']},{item['date']},{item.get('end_date') or item['date']},{pkg}"
        )
    csv_path.write_text("\n".join(lines) + "\n", encoding="utf-8-sig")
    print("csv:", csv_path)

    project = load_json(system_dir(PROJECT) / PROJECT_JSON, {}) or {}
    try:
        project["schedule_csv"] = str(csv_path.relative_to(PROJECT))
        project["schedule_mpp"] = str(dest.relative_to(PROJECT))
    except ValueError:
        project["schedule_csv"] = str(csv_path)
        project["schedule_mpp"] = str(dest)
    save_json(system_dir(PROJECT) / PROJECT_JSON, project)

    for pkg in load_tracker_packages(PROJECT):
        name = pkg.get("package_name") or ""
        nodes = PAYMENT_BY_PACKAGE.get(name)
        if not nodes:
            print("skip:", name)
            continue
        folder = (pkg.get("folder_path") or "").strip()
        if not folder or not Path(folder).is_dir():
            print("missing folder:", name, folder)
            continue
        pkg_dir = Path(folder)
        existing = load_json(pkg_dir / "card-data.json", {}) or {}
        sources = str(existing.get("data_sources") or "").strip()
        suffix = "进度节点按 Master Schedule + PM 指定"
        if suffix not in sources:
            sources = f"{sources}；{suffix}" if sources else suffix
        result = patch_and_render(
            pkg_dir,
            {"payment_nodes": nodes, "data_sources": sources},
        )
        windows = [
            n.get("schedule_window") for n in result["card_data"].get("payment_nodes", [])
        ]
        print(f"OK {name}: {windows}")


if __name__ == "__main__":
    main()
