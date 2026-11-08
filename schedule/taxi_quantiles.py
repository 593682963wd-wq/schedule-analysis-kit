"""作者：Wangyuan；日期：2026-10-29。离线通用核心，输入由调用方显式提供。"""

from __future__ import annotations

from collections import defaultdict

import math

import statistics

PERCENTILE = None

PERCENTILE_COMPARE = None

def _classify_taxi(value, upper_bound):
    if isinstance(value,bool):return None,"非数字"
    try:number=float(value)
    except (TypeError,ValueError):return None,"非数字或空值"
    if not math.isfinite(number):return None,"非数字"
    if number < 0:return None,"负值"
    if number > upper_bound:return None,"超过调用方上界"
    return number,None

def airport_name(value):
    return value

def analyze_rows(
    rows: list[dict],
    percentile: float,
    compare_percentile: float | None,
    *, upper_bound: float,
) -> tuple[dict[str, dict], list[dict]]:
    """对已清洗提取的行做机场分组统计。

    rows: [{airport, flight_no, dep_time, taxi_out(float|None), raw, reason}]
    percentile: 主分位口径；compare_percentile: 对照分位（
    用于与主口径并排对照），传 None 可关闭。
    返回 (airport_stats, removed_rows)。
    """
    if not 0 < percentile <= 1 or (compare_percentile is not None and not 0 < compare_percentile <= 1):raise ValueError("分位须在(0,1]")
    if not math.isfinite(upper_bound) or upper_bound < 0:raise ValueError("上界须有限非负")
    by_airport: dict[str, list[float]] = defaultdict(list)
    removed: list[dict] = []
    for row in rows:
        ap = str(row["airport"] or "").strip().upper()
        reason = row.get("reason")
        value = row.get("taxi_out")
        if not reason:
            # 防御性兜底：即使上游未分类，也按统一口径重新分类，避免脏输入直接进统计
            raw_value = row.get("raw")
            classified, auto_reason = _classify_taxi(
                raw_value if raw_value is not None else value,upper_bound
            )
            if auto_reason is not None:
                reason = auto_reason
                value = None
            else:
                value = classified
        if reason:
            removed.append(
                {
                    "airport": ap,
                    "flight_no": row.get("flight_no") or "",
                    "dep_time": row.get("dep_time") or "",
                    "raw": row.get("raw") if row.get("raw") is not None else "",
                    "reason": reason,
                }
            )
            continue
        if value is None:
            removed.append(
                {
                    "airport": ap,
                    "flight_no": row.get("flight_no") or "",
                    "dep_time": row.get("dep_time") or "",
                    "raw": "",
                    "reason": "滑出时间非数字或空值",
                }
            )
            continue
        by_airport[ap].append(float(value))

    stats: dict[str, dict] = {}
    for ap, values in sorted(by_airport.items()):
        arr = sorted(values)
        n = len(arr)
        if n == 0:
            continue
        rank = math.ceil(percentile * n)
        primary_value = arr[rank - 1]
        covered = sum(1 for v in arr if v <= primary_value)
        if compare_percentile is not None:
            c_rank = math.ceil(compare_percentile * n)
            comparison_value = arr[c_rank - 1]
            covered80 = sum(1 for v in arr if v <= comparison_value)
        else:
            c_rank, comparison_value, covered80 = None, None, None
        removed_for_ap = [r for r in removed if r["airport"] == ap]
        stats[ap] = {
            "airport": ap,
            "airport_name": airport_name(ap),
            "n": n,
            "primary_rank": rank,
            "primary_value": primary_value,
            "coverage": covered / n,
            "comparison_rank": c_rank,
            "comparison_value": comparison_value,
            "comparison_coverage": covered80 / n if covered80 is not None else None,
            "mean": statistics.fmean(arr),
            "median": statistics.median(arr),
            "max": max(arr),
            "min": min(arr),
            "removed_total": len(removed_for_ap),
            "removed_above_bound": sum(1 for r in removed_for_ap if "上界" in str(r["reason"])),
            "removed_negative": sum(1 for r in removed_for_ap if "负" in str(r["reason"])),
            "removed_invalid": sum(1 for r in removed_for_ap if "非数字" in str(r["reason"]) or "空" in str(r["reason"])),
        }
    return stats, removed
