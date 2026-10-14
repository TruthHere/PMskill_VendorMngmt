#!/usr/bin/env python3
"""供应商简称：文件夹名与 Tracker supplier_short 共用。"""

from __future__ import annotations

import re

_FS_BAD = re.compile(r'[\\/:*?"<>|]')
_HAS_LATIN = re.compile(r"[A-Za-z]")
# 长中文名优先掐掉的公司后缀（长的在前）
_CN_SUFFIXES = (
    "股份有限公司",
    "有限责任公司",
    "有限公司",
    "集团公司",
    "集团",
    "公司",
)


def supplier_short_name(name: str, *, max_len: int = 20) -> str:
    """生成供应商简称（约 ≤20 字），供文件夹与 Tracker 共用。

    - 不超过 max_len：整段保留（如 Schneider → Schneider，不再 [:6]）
    - 更长：英文按空格词边界截；中文先去括号段/公司后缀再切，避免半截乱码感
    - 不负责重命名已有包文件夹
    """
    raw = (name or "").strip()
    if not raw or raw == "待确认":
        return "待确认"

    cleaned = _FS_BAD.sub("", raw)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned:
        return "待确认"
    if len(cleaned) <= max_len:
        return cleaned

    # 英文 / 含空格：按词累加，放不下就停在上一词
    if " " in cleaned or _HAS_LATIN.search(cleaned):
        parts = cleaned.split()
        if not parts:
            return "待确认"
        first = parts[0]
        if len(first) > max_len:
            return first[:max_len]
        acc = first
        for part in parts[1:]:
            candidate = f"{acc} {part}"
            if len(candidate) <= max_len:
                acc = candidate
            else:
                break
        return acc

    # 中文无空格：去掉括号说明，再剥公司后缀
    no_paren = re.sub(r"[（(][^）)]*[）)]", "", cleaned).strip() or cleaned
    trimmed = no_paren
    for suffix in _CN_SUFFIXES:
        if trimmed.endswith(suffix) and len(trimmed) > max_len:
            trimmed = trimmed[: -len(suffix)].rstrip(" ·.-")
            break
    if len(trimmed) <= max_len:
        return trimmed or cleaned[:max_len]
    return trimmed[:max_len]


def _self_check() -> None:
    assert supplier_short_name("Schneider") == "Schneider", supplier_short_name("Schneider")
    assert supplier_short_name("Schneider") != "Schnei"
    assert supplier_short_name("BOSCH Building Technologies").startswith("BOSCH")
    assert len(supplier_short_name("BOSCH Building Technologies")) <= 20
    # 中文：短名整段保留；超长不切出半个「公」之类的无意义尾巴优先剥后缀
    assert supplier_short_name("施耐德电气") == "施耐德电气"
    long_cn = "上海某某机电设备工程技术服务有限公司"
    short_cn = supplier_short_name(long_cn)
    assert len(short_cn) <= 20
    assert not short_cn.endswith("公")  # 不应只剩半个后缀
    assert supplier_short_name("") == "待确认"
    assert supplier_short_name("待确认") == "待确认"
    print("supplier_naming self-check OK")


if __name__ == "__main__":
    _self_check()
