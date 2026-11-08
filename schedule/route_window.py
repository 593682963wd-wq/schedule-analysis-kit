"""作者：Wangyuan；日期：2026-10-29。离线通用核心，输入由调用方显式提供。"""

from __future__ import annotations
import re
import math

def parse_schedule(sched_str: str) -> str:
    return ''.join(c for c in str(sched_str) if c.isdigit())

def time_to_minutes(t_str: str) -> int | None:
    if isinstance(t_str,bool):return None
    raw=str(t_str).strip()
    if re.fullmatch(r"[0-9]{3,4}\.0",raw):raw=raw[:-2]
    match=re.fullmatch(r"([0-9]{1,2}):?([0-9]{2})",raw)
    if not match:return None
    hour,minute=map(int,match.groups())
    return hour*60+minute if 0<=hour<24 and 0<=minute<60 else None


def within_n_hours(t1: str, t2: str, hours: int = 1) -> bool:
    if not math.isfinite(hours) or hours<0:raise ValueError("窗口必须有限非负")
    m1, m2 = time_to_minutes(t1), time_to_minutes(t2)
    if m1 is None or m2 is None:
        return False
    diff = abs(m1 - m2)
    if not 0 <= m1 < 1440 or not 0 <= m2 < 1440 or hours < 0:
        raise ValueError("时刻须为一天内合法时刻，窗口不能为负")
    return min(diff, 1440 - diff) <= hours * 60
