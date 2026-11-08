"""作者：Wangyuan；日期：2026-10-29。离线通用核心，输入由调用方显式提供。"""

from __future__ import annotations

from collections import defaultdict

from dataclasses import dataclass, field

from statistics import mean

from typing import Any

import datetime as dt

import re

AREAS = ()

MODE_ORDER = ()

METRICS = (
    ("taxi_in_avg", "平均滑入时间"),
    ("taxi_out_avg", "平均滑出时间"),
    ("taxi_total_avg", "平均滑行时间"),
)

@dataclass
class RunwayNormalization:
    landing_runway: str | None
    takeoff_runway: str | None
    mode: str | None
    notes: list[str] = field(default_factory=list)

@dataclass
class TaxiRecord:
    source_row: int
    stand: str
    landing_runway_raw: str
    takeoff_runway_raw: str
    landing_runway: str
    takeoff_runway: str
    mode_raw: str
    mode: str
    taxi_in_seconds: float | None
    taxi_out_seconds: float | None
    taxi_total_seconds: float | None
    correction_notes: list[str] = field(default_factory=list)

@dataclass
class StandModeStats:
    mode: str
    stand: str
    sample_count: int
    taxi_in_avg: float | None
    taxi_out_avg: float | None
    taxi_total_avg: float | None
    taxi_in_count: int
    taxi_out_count: int
    taxi_total_count: int

@dataclass
class OverallStats:
    valid_records: int
    taxi_in_avg: float | None
    taxi_out_avg: float | None
    taxi_total_avg: float | None
    taxi_in_count: int
    taxi_out_count: int
    taxi_total_count: int

def display_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()

def normalize_stand(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        text = str(int(value))
    elif isinstance(value, int):
        text = str(value)
    else:
        text = str(value).strip()
    text = text.replace(" ", "").upper()
    if text.endswith(".0") and text[:-2].isdigit():
        text = text[:-2]
    return text

def parse_time_to_seconds(value: Any) -> float | None:
    if value in (None, "", "--"):
        return None
    if isinstance(value, dt.datetime):
        value = value.time()
    if isinstance(value, dt.time):
        return value.hour * 3600 + value.minute * 60 + value.second + value.microsecond / 1_000_000
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        number = float(value)
        if 0 <= number < 1:
            return number * 86400
        return None
    text = display_value(value)
    if not text or text.startswith("="):
        return None
    if " " in text:
        text = text.split()[-1]
    text = text.replace("：", ":")
    parts = text.split(":")
    if len(parts) == 3 and all(part.strip().isdigit() for part in parts):
        hour, minute, second = (int(part) for part in parts)
        if 0 <= minute < 60 and 0 <= second < 60:
            return hour * 3600 + minute * 60 + second
    if len(parts) == 2 and all(part.strip().isdigit() for part in parts):
        minute, second = (int(part) for part in parts)
        if 0 <= second < 60:
            return minute * 60 + second
    return None

def natural_stand_key(stand: str) -> tuple[int, int, str]:
    text = normalize_stand(stand)
    match = re.match(r"^(\d+)([A-Z]*)$", text)
    if not match:
        return (10**9, 1, text)
    number = int(match.group(1))
    suffix = match.group(2)
    suffix_order = {"L": 0, "": 1, "R": 2}.get(suffix, 3)
    return (number, suffix_order, suffix)

def build_overall_stats(records: list[TaxiRecord]) -> OverallStats:
    taxi_in_values = [record.taxi_in_seconds for record in records if record.taxi_in_seconds is not None]
    taxi_out_values = [record.taxi_out_seconds for record in records if record.taxi_out_seconds is not None]
    taxi_total_values = [record.taxi_total_seconds for record in records if record.taxi_total_seconds is not None]
    return OverallStats(
        valid_records=len(records),
        taxi_in_avg=safe_mean(taxi_in_values),
        taxi_out_avg=safe_mean(taxi_out_values),
        taxi_total_avg=safe_mean(taxi_total_values),
        taxi_in_count=len(taxi_in_values),
        taxi_out_count=len(taxi_out_values),
        taxi_total_count=len(taxi_total_values),
    )

def build_mode_stats(records: list[TaxiRecord]) -> dict[str, list[StandModeStats]]:
    grouped: dict[tuple[str, str], list[TaxiRecord]] = defaultdict(list)
    for record in records:
        grouped[(record.mode, record.stand)].append(record)

    stats_by_mode: dict[str, list[StandModeStats]] = {mode: [] for mode in MODE_ORDER}
    for (mode, stand), group in grouped.items():
        taxi_in_values = [record.taxi_in_seconds for record in group if record.taxi_in_seconds is not None]
        taxi_out_values = [record.taxi_out_seconds for record in group if record.taxi_out_seconds is not None]
        taxi_total_values = [record.taxi_total_seconds for record in group if record.taxi_total_seconds is not None]
        stats_by_mode.setdefault(mode, []).append(
            StandModeStats(
                mode=mode,
                stand=stand,
                sample_count=len(group),
                taxi_in_avg=safe_mean(taxi_in_values),
                taxi_out_avg=safe_mean(taxi_out_values),
                taxi_total_avg=safe_mean(taxi_total_values),
                taxi_in_count=len(taxi_in_values),
                taxi_out_count=len(taxi_out_values),
                taxi_total_count=len(taxi_total_values),
            )
        )

    for stats in stats_by_mode.values():
        stats.sort(key=lambda item: natural_stand_key(item.stand))
    return stats_by_mode

def safe_mean(values: list[float]) -> float | None:
    return mean(values) if values else None

def build_area_rankings(
    mode_stats: dict[str, list[StandModeStats]],
    *, areas: list[tuple[str,str,list[str]]],
) -> dict[str, dict[str, dict[str, list[tuple[str, float]]]]]:
    rankings: dict[str, dict[str, dict[str, list[tuple[str, float]]]]] = {}
    for mode in mode_stats:
        stats_by_stand = {stat.stand: stat for stat in mode_stats.get(mode, [])}
        mode_rankings: dict[str, dict[str, list[tuple[str, float]]]] = {}
        for area_id, _, stands in areas:
            metric_rankings: dict[str, list[tuple[str, float]]] = {}
            for metric_name, _ in METRICS:
                rows: list[tuple[str, float]] = []
                for stand in stands:
                    stat = stats_by_stand.get(stand)
                    value = getattr(stat, metric_name) if stat else None
                    if value is not None:
                        rows.append((stand, value))
                rows.sort(key=lambda item: (item[1], natural_stand_key(item[0])))
                metric_rankings[metric_name] = rows
            mode_rankings[area_id] = metric_rankings
        rankings[mode] = mode_rankings
    return rankings
