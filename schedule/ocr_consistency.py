"""作者：Wangyuan；日期：2026-10-29。离线通用核心，输入由调用方显式提供。"""

from __future__ import annotations

from dataclasses import dataclass

import re

@dataclass
class OcrItem:
    text: str
    x: float
    y: float
    w: float
    h: float

def compact_text(text: str) -> str:
    return re.sub(r"\s+", "", (text or "").strip())

def dedupe_ocr_items(items: list[OcrItem]) -> list[OcrItem]:
    deduped: list[OcrItem] = []
    seen: set[tuple[str, int, int]] = set()
    for item in items:
        key = (compact_text(item.text), round(item.x * 100), round(item.y * 100))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped

def ratio_from_count(count: int | None, total: int | None) -> float | None:
    if count is None or not total:
        return None
    return round(count / total * 100, 2)

def validated_cancel_total(
    total: int | None,
    pairs: list[tuple[int | None, float | None]],
    *, absolute_tolerance: float, relative_tolerance: float,
) -> int | None:
    if total is None or total <= 0:
        return None
    for count, rate in pairs:
        if count is None:
            continue
        if count > total:
            return None
        if rate is None:
            continue
        computed = ratio_from_count(count, total)
        if computed is None:
            continue
        tolerance = max(absolute_tolerance, abs(rate) * relative_tolerance)
        if abs(computed - rate) > tolerance:
            return None
    return total
