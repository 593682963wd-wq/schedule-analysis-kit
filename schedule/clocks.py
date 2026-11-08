"""作者：Wangyuan；日期：2026-10-29。离线通用核心，输入由调用方显式提供。"""

from __future__ import annotations

from typing import Any

import datetime as dt

import re

class DelayCrewDutyError(ValueError):
    """延误值勤工具可安全展示给用户的输入或业务错误。"""

def _coerce_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None

def parse_clock_minutes(value: Any, *, field_name: str = "时间") -> int | None:
    """解析时刻，允许 `25:30` 这类跨日累计写法。

    Excel 小于 1 的数值按一天分数处理；纯三/四位数字按 HHMM 处理。
    空值返回 ``None``，非法非空值抛出可展示错误。
    """

    if value is None or value == "":
        return None
    if isinstance(value, dt.datetime):
        return value.hour * 60 + value.minute
    if isinstance(value, dt.time):
        return value.hour * 60 + value.minute
    number = _coerce_number(value)
    text = str(value).strip().replace("：", ":")
    if ":" not in text and number is not None and 0 <= number < 1:
        return round(number * 24 * 60)
    if ":" in text:
        match = re.fullmatch(r"\s*(\d{1,3}):(\d{1,2})\s*", text)
        if not match:
            raise DelayCrewDutyError(f"{field_name}格式应为 HH:MM，可跨日写 25:30。")
        hour, minute = int(match.group(1)), int(match.group(2))
        if hour > 72 or minute > 59:
            raise DelayCrewDutyError(f"{field_name}超出可接受范围。")
        return hour * 60 + minute
    if re.fullmatch(r"\d{3,4}", text):
        digits = text.zfill(4)
        hour, minute = int(digits[:-2]), int(digits[-2:])
        if hour <= 72 and minute <= 59:
            return hour * 60 + minute
    raise DelayCrewDutyError(f"{field_name}格式应为 HH:MM，可跨日写 25:30。")

def parse_duration_minutes(value: Any, *, field_name: str = "时长") -> int | None:
    """解析时长，支持 Excel 天数、小时数或 `HH:MM`。"""

    if value is None or value == "":
        return None
    if isinstance(value, dt.timedelta):
        minutes = round(value.total_seconds() / 60)
        if minutes < 0:
            raise DelayCrewDutyError(f"{field_name}不能为负数。")
        return minutes
    text = str(value).strip().replace("：", ":")
    number = _coerce_number(value)
    if ":" in text:
        match = re.fullmatch(r"\s*(\d{1,3}):(\d{1,2})\s*", text)
        if not match:
            raise DelayCrewDutyError(f"{field_name}格式应为小时:分钟。")
        hour, minute = int(match.group(1)), int(match.group(2))
        if hour > 72 or minute > 59:
            raise DelayCrewDutyError(f"{field_name}超出可接受范围。")
        return hour * 60 + minute
    if number is not None:
        if number < 0:
            raise DelayCrewDutyError(f"{field_name}不能为负数。")
        if number < 1:
            return round(number * 24 * 60)
        if number <= 72:
            return round(number * 60)
    raise DelayCrewDutyError(f"{field_name}格式应为小时数或 HH:MM。")

def format_clock(minutes: int | None) -> str:
    """把绝对分钟显示为累计 HH:MM，不丢失跨日信息。"""

    if minutes is None:
        return ""
    sign = "-" if minutes < 0 else ""
    value = abs(int(minutes))
    return f"{sign}{value // 60:02d}:{value % 60:02d}"

def format_duration(minutes: int | None) -> str:
    """把带符号分钟显示为 H:MM。"""

    if minutes is None:
        return ""
    sign = "-" if minutes < 0 else ""
    value = abs(int(minutes))
    return f"{sign}{value // 60}:{value % 60:02d}"

def _align_not_before(value: int, anchor: int) -> int:
    aligned = value
    while aligned < anchor:
        aligned += 24 * 60
    return aligned

def interval_minutes(start: int | None, end: int | None) -> tuple[int | None, str | None]:
    """计算一段退场/进场时长；单边缺失时返回待补提示。"""

    if start is None and end is None:
        return 0, None
    if start is None or end is None:
        return None, "退场和进场时间需成对填写"
    aligned_end = _align_not_before(end, start)
    duration = aligned_end - start
    if duration > 24 * 60:
        return None, "单次休息时长超过 24 小时，请复核"
    return duration, None
