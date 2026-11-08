"""作者：Wangyuan；日期：2026-10-29。离线通用核心，输入由调用方显式提供。"""

from __future__ import annotations
import math

from dataclasses import dataclass

from typing import Optional

@dataclass
class SegmentStat:
    weighted_sum: float = 0.0
    weight_sum: float = 0.0
    sample_count: int = 0

    def add(self, minutes: float, weight: float) -> None:
        if not math.isfinite(minutes) or not math.isfinite(weight) or minutes < 0 or weight <= 0:
            raise ValueError("时长必须有限非负，权重必须有限为正")
        self.weighted_sum += minutes * weight
        self.weight_sum += weight
        self.sample_count += 1

    def avg_minutes(self) -> Optional[int]:
        if self.weight_sum <= 0:
            return None
        return int(round(self.weighted_sum / self.weight_sum))

def normalize_route(route_text: str) -> str:
    text = str(route_text).strip().replace("—", "-").replace("－", "-").replace("–", "-")
    text = "".join(ch for ch in text if ch not in (" ", "\t", "\n", "\r"))
    return text

def calc_duration(start_min: Optional[int], end_min: Optional[int]) -> Optional[int]:
    if start_min is None or end_min is None:
        return None
    if end_min < start_min:
        end_min += 24 * 60
    return end_min - start_min

def nearest_5(minutes: int) -> int:
    lower = (minutes // 5) * 5
    upper = lower + 5
    return lower if (minutes - lower) <= (upper - minutes) else upper
