"""作者：Wangyuan；日期：2026-10-29。离线通用核心，输入由调用方显式提供。"""

from __future__ import annotations

from collections import Counter, defaultdict

from dataclasses import dataclass, field

from typing import Iterable, Optional

def load_flights(rows):
    return rows, {}

def _fmt(m: Optional[int]) -> str:
    if m is None:
        return "-"
    m = m % 1440
    return f"{m // 60:02d}:{m % 60:02d}"

@dataclass
class FlightRow:
    row_no: int
    flight_no: str
    tail: Optional[int]
    overnight: str
    route: str
    days: list[int]
    legs: list[dict] = field(default_factory=list)

    @property
    def first_dep(self) -> str:
        return self.legs[0]["dep"] if self.legs else ""

    @property
    def last_arr(self) -> str:
        return self.legs[-1]["arr"] if self.legs else ""

    @property
    def first_std(self) -> Optional[int]:
        return self.legs[0]["std_min"] if self.legs else None

    @property
    def last_sta(self) -> Optional[int]:
        return self.legs[-1]["sta_min"] if self.legs else None

    @property
    def block_minutes(self) -> Optional[int]:
        if not self.legs:
            return None
        total = 0
        for lg in self.legs:
            s, e = lg["std_min"], lg["sta_min"]
            if s is None or e is None:
                return None
            d = e - s
            if d < 0:
                d += 1440
            total += d
        return total

def daily_count(flights: list[FlightRow]) -> dict:
    by_day_seg: dict[int, int] = defaultdict(int)
    by_day_row: dict[int, int] = defaultdict(int)
    weekly_segs = weekly_rows = 0
    for f in flights:
        seg = len(f.legs)
        for d in f.days:
            by_day_seg[d] += seg
            by_day_row[d] += 1
        weekly_segs += seg * len(f.days)
        weekly_rows += len(f.days)
    return {
        "total_rows": len(flights),
        "total_segments_per_day_avg": round(weekly_segs / 7, 1),
        "total_flights_per_day_avg": round(weekly_rows / 7, 1),
        "weekly_segments": weekly_segs,
        "by_day_segments": dict(sorted(by_day_seg.items())),
        "by_day_flights": dict(sorted(by_day_row.items())),
    }

def utilization(flights: list[FlightRow]) -> dict:
    per_tail_min: dict[int, int] = defaultdict(int)
    for f in flights:
        if f.tail is None:
            continue
        bm = f.block_minutes
        if bm is None:
            continue
        per_tail_min[f.tail] += bm * len(f.days)
    util = {t: round(total / 7 / 60, 2) for t, total in per_tail_min.items()}
    if util:
        avg = round(sum(util.values()) / len(util), 2)
    else:
        avg = 0.0
    return {
        "per_tail": dict(sorted(util.items())),
        "tail_count": len(util),
        "avg_hours_per_day": avg,
        "max_hours_per_day": max(util.values()) if util else 0,
        "min_hours_per_day": min(util.values()) if util else 0,
    }

def compare_versions(old_path: list[FlightRow], new_path: list[FlightRow]) -> dict:
    old_fl, _ = load_flights(old_path)
    new_fl, _ = load_flights(new_path)
    if len({f.flight_no for f in old_fl}) != len(old_fl) or len({f.flight_no for f in new_fl}) != len(new_fl):
        raise ValueError("版本比较需要唯一航班标识")
    old_idx = {f.flight_no: f for f in old_fl}
    new_idx = {f.flight_no: f for f in new_fl}
    added = sorted(set(new_idx) - set(old_idx))
    removed = sorted(set(old_idx) - set(new_idx))
    changed = []
    for fno in sorted(set(old_idx) & set(new_idx)):
        a, b = old_idx[fno], new_idx[fno]
        diffs = []
        if a.route != b.route:
            diffs.append(f"航线 {a.route}→{b.route}")
        if a.first_std != b.first_std:
            diffs.append(f"STD {_fmt(a.first_std)}→{_fmt(b.first_std)}")
        if a.last_sta != b.last_sta:
            diffs.append(f"STA {_fmt(a.last_sta)}→{_fmt(b.last_sta)}")
        if sorted(a.days) != sorted(b.days):
            diffs.append(f"班期 {a.days}→{b.days}")
        if diffs:
            changed.append({"flight": fno, "changes": "; ".join(diffs)})
    return {"added_count": len(added), "removed_count": len(removed),
            "changed_count": len(changed),
            "added": added, "removed": removed, "changed": changed}
