"""作者：Wangyuan；日期：2026-10-29。离线通用核心，输入由调用方显式提供。"""

from __future__ import annotations

from dataclasses import dataclass

from datetime import date, datetime, time

from statistics import mean

from typing import Any, Optional

@dataclass
class AirportStats:
    airport_code: str
    airport_name: str
    airport_full_name: str
    taxi_out_values: list[int]
    taxi_in_values: list[int]
    actual_guarantee_values: list[int]
    actual_turnaround_values: list[int]
    ground_service_values: list[int]

    @property
    def taxi_out_avg(self) -> Optional[float]:
        return round(mean(self.taxi_out_values), 1) if self.taxi_out_values else None

    @property
    def taxi_in_avg(self) -> Optional[float]:
        return round(mean(self.taxi_in_values), 1) if self.taxi_in_values else None

    @property
    def taxi_total_avg(self) -> Optional[float]:
        if self.taxi_out_avg is None or self.taxi_in_avg is None:
            return None
        return round((self.taxi_out_avg or 0) + (self.taxi_in_avg or 0), 1)

    @property
    def actual_guarantee_avg(self) -> Optional[float]:
        return round(mean(self.actual_guarantee_values), 1) if self.actual_guarantee_values else None

    @property
    def actual_turnaround_avg(self) -> Optional[float]:
        return round(mean(self.actual_turnaround_values), 1) if self.actual_turnaround_values else None

    @property
    def ground_service_avg(self) -> Optional[float]:
        return round(mean(self.ground_service_values), 1) if self.ground_service_values else None

    @property
    def taxi_sample_count(self) -> int:
        return len(self.taxi_out_values) + len(self.taxi_in_values)

def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()

def parse_clock_minutes(value: Any) -> Optional[int]:
    if value in (None, "", "--"):
        return None
    if isinstance(value, datetime):
        return value.hour * 60 + value.minute
    if isinstance(value, time):
        return value.hour * 60 + value.minute
    if isinstance(value, float) and 0 <= value < 1:
        return int(round(value * 24 * 60)) % (24 * 60)

    text = normalize_text(value)
    if not text or text == "--":
        return None
    if " " in text:
        text = text.split()[-1]
    if ":" in text:
        parts = text.split(":")
        if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
            hour = int(parts[0])
            minute = int(parts[1])
            if 0 <= hour <= 47 and 0 <= minute <= 59:
                return hour * 60 + minute
    return None

def parse_duration_minutes(value: Any) -> Optional[int]:
    if value in (None, "", "--"):
        return None
    if isinstance(value, (int, float)):
        minutes = int(round(value))
        return minutes if minutes >= 0 else None
    text = normalize_text(value)
    if not text or text == "--":
        return None
    if text.isdigit():
        return int(text)
    return None

def is_valid_minutes(value: Optional[int], upper_bound: int) -> bool:
    return value is not None and 0 < value <= upper_bound

def absolute_minutes(day_value: date, minute_of_day: int) -> int:
    return day_value.toordinal() * 24 * 60 + minute_of_day

def normalize_forward(candidate_abs: Optional[int], reference_abs: Optional[int], tolerance_minutes: int = 0) -> Optional[int]:
    if candidate_abs is None:
        return None
    if reference_abs is not None and candidate_abs < (reference_abs - tolerance_minutes):
        return candidate_abs + 24 * 60
    return candidate_abs

def normalize_backward_or_same(candidate_abs: Optional[int], reference_abs: Optional[int], tolerance_minutes: int = 0) -> Optional[int]:
    if candidate_abs is None:
        return None
    if reference_abs is not None and candidate_abs > (reference_abs + tolerance_minutes):
        return candidate_abs - 24 * 60
    return candidate_abs

def pick_taxi_in_metrics(
    base_date: Optional[date],
    arrival_time: Any,
    taxi_in_time: Any,
    taxi_in_raw: Any,
    arrival_abs_reference: Optional[int] = None,
) -> tuple[Optional[int], Optional[int], Optional[str]]:
    arrival_min = parse_clock_minutes(arrival_time)
    if base_date is None or arrival_min is None:
        return None, None, "缺少时间"

    arrival_abs = arrival_abs_reference
    if arrival_abs is None:
        arrival_abs = absolute_minutes(base_date, arrival_min)

    taxi_in_clock = parse_clock_minutes(taxi_in_time)
    if taxi_in_clock is not None:
        taxi_in_abs = normalize_forward(absolute_minutes(base_date, taxi_in_clock), arrival_abs)
        if taxi_in_abs is not None:
            return taxi_in_abs - arrival_abs, taxi_in_abs, None

    raw_clock = parse_clock_minutes(taxi_in_raw)
    if raw_clock is not None:
        taxi_in_abs = normalize_forward(absolute_minutes(base_date, raw_clock), arrival_abs)
        if taxi_in_abs is not None:
            return taxi_in_abs - arrival_abs, taxi_in_abs, None

    raw_duration = parse_duration_minutes(taxi_in_raw)
    if raw_duration is not None:
        return raw_duration, arrival_abs + raw_duration, None

    return None, None, "缺少时间"

def pick_latest_close_abs(base_date: Optional[date], push_abs: Optional[int], cabin_value: Any, cargo_value: Any) -> Optional[int]:
    if base_date is None:
        return None
    candidates: list[int] = []
    for value in (cabin_value, cargo_value):
        minute_value = parse_clock_minutes(value)
        if minute_value is None:
            continue
        absolute = absolute_minutes(base_date, minute_value)
        absolute = normalize_backward_or_same(absolute, push_abs, tolerance_minutes=30)
        if absolute is not None:
            candidates.append(absolute)
    return max(candidates) if candidates else None

def pick_earliest_open_abs(base_date: Optional[date], reference_abs: Optional[int], cabin_value: Any, cargo_value: Any) -> Optional[int]:
    if base_date is None or reference_abs is None:
        return None
    candidates: list[int] = []
    for value in (cabin_value, cargo_value):
        minute_value = parse_clock_minutes(value)
        if minute_value is None:
            continue
        absolute = normalize_forward(absolute_minutes(base_date, minute_value), reference_abs, tolerance_minutes=30)
        if absolute is not None:
            candidates.append(absolute)
    return min(candidates) if candidates else None

def evaluate_turn_metric(
    value: Optional[int],
    limit: int,
    excluded_by_pair: bool,
    missing_counter_key: str,
    invalid_counter_key: str,
    valid_counter_key: str,
    summary: dict[str, Any],
    notes: list[str],
    label: str,
) -> bool:
    if value is None:
        summary[missing_counter_key] += 1
        notes.append(f"{label}缺少时间")
        return False
    if excluded_by_pair:
        return False
    if not is_valid_minutes(value, limit):
        summary[invalid_counter_key] += 1
        notes.append(f"{label}异常({value})")
        return False
    summary[valid_counter_key] += 1
    return True
