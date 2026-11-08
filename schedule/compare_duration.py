"""作者：Wangyuan；日期：2026-10-29。显式记录与参考时长的闭环比较。"""
from __future__ import annotations
from collections import defaultdict
from typing import Any, Iterable, Mapping
import math
from .time_math import SegmentStat, calc_duration
from .clocks import parse_clock_minutes


def weighted_history(rows: Iterable[Mapping[str, Any]]) -> dict[tuple[str,str], int]:
    """累积有向区间的加权时长；不自动合并同城地点或补造权重。"""
    grouped: dict[tuple[str,str], SegmentStat] = defaultdict(SegmentStat)
    for row in rows:
        key = (str(row["origin"]).strip(), str(row["destination"]).strip())
        if not all(key):
            raise ValueError("区间端点不能为空")
        grouped[key].add(float(row["duration"]), float(row["weight"]))
    return {key: stat.avg_minutes() for key, stat in grouped.items()}


def compare_durations(rows: Iterable[Mapping[str, Any]], history: Mapping[tuple[str,str], int], *, gap_boundaries: tuple[float,...]) -> list[dict[str,Any]]:
    """逐段保留参考缺失和时刻缺失，等级仅按调用方边界编号。"""
    if any(not math.isfinite(x) for x in gap_boundaries) or tuple(sorted(set(gap_boundaries))) != gap_boundaries:
        raise ValueError("边界必须有限、严格递增")
    output=[]
    for row in rows:
        key=(str(row["origin"]).strip(),str(row["destination"]).strip())
        planned=calc_duration(parse_clock_minutes(row.get("departure")),parse_clock_minutes(row.get("arrival")))
        reference=history.get(key)
        if reference is not None and (not math.isfinite(reference) or reference<0):
            raise ValueError("参考时长必须有限非负")
        gap=reference-planned if reference is not None and planned is not None else None
        output.append({"id": str(row["id"]),"origin":key[0],"destination":key[1],"planned_minutes":planned,"reference_minutes":reference,"gap_minutes":gap,"band":sum(gap>x for x in gap_boundaries) if gap is not None else None})
    return output
