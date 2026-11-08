"""作者：Wangyuan；日期：2026-10-29。基于显式航段记录的时间窗筛选。"""
from __future__ import annotations
from collections import defaultdict
import re
from .route_window import within_n_hours,time_to_minutes


def filter_segments(all_segments: list[dict], *, carrier_prefix: str, hours: int, running_routes: set[tuple[str,str]] | None = None, excluded_prefixes: set[str] | None = None) -> dict:
    """保留同向区间且落入目标窗口的其他前缀航段；日界按24小时圆环。"""
    if not carrier_prefix or hours < 0: raise ValueError("前缀和时间窗必须有效")
    excluded_prefixes=excluded_prefixes or set()
    # --- group by route ---
    route_segs = defaultdict(list)
    for s in all_segments:
        route_segs[(s['origin'], s['dest'])].append(s)

    target_routes = defaultdict(list)
    for s in all_segments:
        if s['fn'].startswith(carrier_prefix):
            target_routes[(s['origin'], s['dest'])].append(s)

    # --- filter ±N hours, running routes, 独飞 ---
    route_results: dict[tuple, list] = {}
    independent_count = 0
    skipped_not_running = 0

    for rk, target_segs in target_routes.items():
        # ① 运行航线过滤
        if running_routes is not None:
            o_city = rk[0]
            d_city = rk[1]
            o_variants = {o_city, o_city}
            d_variants = {d_city, d_city}
            matched = any(
                (ov, dv) in running_routes
                for ov in o_variants
                for dv in d_variants
            )
            if not matched:
                skipped_not_running += 1
                continue

        # ② 竞飞筛选
        target_deps = [s['dep'] for s in target_segs]
        filtered = []
        for s in route_segs[rk]:
            if s['fn'].startswith(carrier_prefix):
                filtered.append(s)
            else:
                pfx = re.match(r'^([A-Z]+)', s['fn'])
                if pfx and pfx.group(1) in excluded_prefixes:
                    continue
                if any(within_n_hours(s['dep'], od, hours) for od in target_deps):
                    filtered.append(s)

        # ③ 独飞航线排除——只有目标前缀自身，不算竞飞
        others = [s for s in filtered if not s['fn'].startswith(carrier_prefix)]
        if not others:
            independent_count += 1
            continue

        filtered.sort(key=lambda x: time_to_minutes(x['dep']) or 0)
        route_results[rk] = filtered

    return {"routes":[{"origin":o,"destination":d,"segments":rows} for (o,d),rows in sorted(route_results.items())],"independent_routes":independent_count,"skipped_not_running":skipped_not_running}
