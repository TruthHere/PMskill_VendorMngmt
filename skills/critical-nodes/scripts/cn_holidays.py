"""中国工装现场常用长假停工区间（自然日默认，零依赖）。

规则（PM 现场经验默认，非国务院当年调休公告）：
- 春节停工：除夕前 15 天（含）～正月十五（含）
- 五一：5/1～5/5
- 十一：10/1～10/7

春节依赖「正月初一」公历日表（查历得到）；覆盖约 2020–2037。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterable


# 正月初一（公历月, 日）— 农历查历结果，按年扩展即可
_CNY_DAY1: dict[int, tuple[int, int]] = {
    2020: (1, 25),
    2021: (2, 12),
    2022: (2, 1),
    2023: (1, 22),
    2024: (2, 10),
    2025: (1, 29),
    2026: (2, 17),
    2027: (2, 6),
    2028: (1, 26),
    2029: (2, 13),
    2030: (2, 3),
    2031: (1, 23),
    2032: (2, 11),
    2033: (1, 31),
    2034: (2, 19),
    2035: (2, 8),
    2036: (1, 28),
    2037: (2, 15),
}


@dataclass(frozen=True)
class HolidayBand:
    kind: str  # spring | labor | national
    name: str
    start: date
    end: date  # inclusive
    note: str = ""

    def clipped(self, axis_start: date, axis_end: date) -> HolidayBand | None:
        s = max(self.start, axis_start)
        e = min(self.end, axis_end)
        if e < s:
            return None
        return HolidayBand(self.kind, self.name, s, e, self.note)


def spring_festival_eve(year: int) -> date | None:
    """除夕 = 正月初一前一天。year 指春节所在公历年（正月初一所在年）。"""
    md = _CNY_DAY1.get(year)
    if not md:
        return None
    day1 = date(year, md[0], md[1])
    return day1 - timedelta(days=1)


def spring_festival_band(year: int) -> HolidayBand | None:
    eve = spring_festival_eve(year)
    if not eve:
        return None
    day1 = eve + timedelta(days=1)
    lantern = day1 + timedelta(days=14)  # 正月十五
    start = eve - timedelta(days=15)
    return HolidayBand(
        kind="spring",
        name=f"春节停工 {year}",
        start=start,
        end=lantern,
        note="除夕前15天～正月十五（现场默认无人）",
    )


def labor_day_band(year: int) -> HolidayBand:
    return HolidayBand(
        kind="labor",
        name=f"五一 {year}",
        start=date(year, 5, 1),
        end=date(year, 5, 5),
        note="默认 5/1～5/5",
    )


def national_day_band(year: int) -> HolidayBand:
    return HolidayBand(
        kind="national",
        name=f"十一 {year}",
        start=date(year, 10, 1),
        end=date(year, 10, 7),
        note="默认 10/1～10/7",
    )


def _years_touching(axis_start: date, axis_end: date) -> list[int]:
    # 春节色带可能从上年 12 月跨到本年；多取前后一年
    years = set(range(axis_start.year - 1, axis_end.year + 2))
    return sorted(years)


def holiday_bands_for_axis(
    axis_start: date,
    axis_end: date,
    *,
    include_spring: bool = True,
    include_labor: bool = True,
    include_national: bool = True,
) -> list[HolidayBand]:
    """返回与时间轴相交的停工/长假色带（已裁剪到轴范围内）。"""
    out: list[HolidayBand] = []
    for y in _years_touching(axis_start, axis_end):
        candidates: list[HolidayBand | None] = []
        if include_spring:
            candidates.append(spring_festival_band(y))
        if include_labor:
            candidates.append(labor_day_band(y))
        if include_national:
            candidates.append(national_day_band(y))
        for band in candidates:
            if band is None:
                continue
            clipped = band.clipped(axis_start, axis_end)
            if clipped:
                out.append(clipped)
    out.sort(key=lambda b: (b.start, b.end, b.kind))
    return out


def bands_to_dicts(bands: Iterable[HolidayBand]) -> list[dict]:
    return [
        {
            "kind": b.kind,
            "name": b.name,
            "start": b.start.isoformat(),
            "end": b.end.isoformat(),
            "note": b.note,
        }
        for b in bands
    ]
