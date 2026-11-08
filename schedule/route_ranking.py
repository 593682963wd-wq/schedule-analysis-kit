"""作者：Wangyuan；日期：2026-10-29。离线通用核心，输入由调用方显式提供。"""

from __future__ import annotations

from dataclasses import dataclass, field

from typing import Iterable

import re

def short_city(value):
    return str(value).strip()

@dataclass
class RouteStats:
    """双向聚合后的航线统计。"""

    route: str  # 字典序后的双向键，以调用方端点名称构成
    city_a: str
    city_b: str
    flight_nos: set[str] = field(default_factory=set)
    counts: dict[str, dict[str, int]] = field(default_factory=dict)
    cities_are_short: bool = False
    # counts['general'] = {'ok': 14, 'bad': 1}

    def rate(self, metric: str) -> float:
        c = self.counts.get(metric, {"ok": 0, "bad": 0})
        total = c["ok"] + c["bad"]
        if total == 0:
            return 0.0
        return c["ok"] / total * 100.0

    def total(self, metric: str) -> int:
        c = self.counts.get(metric, {"ok": 0, "bad": 0})
        return c["ok"] + c["bad"]

    def ok(self, metric: str) -> int:
        return self.counts.get(metric, {"ok": 0, "bad": 0})["ok"]

    def bad(self, metric: str) -> int:
        return self.counts.get(metric, {"ok": 0, "bad": 0})["bad"]

def _split_terms(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"[\n,，;；|]+", text or "") if part.strip()]

def _pair_from_term(term: str) -> tuple[str, str] | None:
    normalized = term.strip().replace("＝", "=").replace("→", "-").replace("—", "-").replace("–", "-")
    parts = [part.strip() for part in re.split(r"\s*(?:=|->|-)\s*", normalized) if part.strip()]
    if len(parts) != 2:
        parts = [part.strip() for part in re.split(r"\s*至\s*", normalized) if part.strip()]
    if len(parts) != 2 or not all(parts):
        return None
    return parts[0], parts[1]

def _route_matches_term(city_a: str, city_b: str, term: str) -> bool:
    pair = _pair_from_term(term)
    if pair:
        q1, q2 = pair
        return (
            (_match_city(q1, city_a) and _match_city(q2, city_b))
            or (_match_city(q1, city_b) and _match_city(q2, city_a))
        )
    return _match_city(term, city_a) or _match_city(term, city_b)

def _stats_in_scope(stats: RouteStats, scope_text: str) -> bool:
    terms = _split_terms(scope_text)
    return not terms or any(_route_matches_term(stats.city_a, stats.city_b, term) for term in terms)

def rank(stats: Iterable[RouteStats], *, scope_text: str = "") -> list[dict]:
    """按调用方已分类的计数占比升序排名（最低 = 第 1 名）。返回字典列表方便 UI 用。"""
    items = [s for s in stats if s.total("general") > 0 and _stats_in_scope(s, scope_text)]
    items.sort(key=lambda s: (s.rate("general"), -s.total("general"), s.route))
    out: list[dict] = []
    for i, s in enumerate(items, start=1):
        sa = s.city_a if s.cities_are_short else short_city(s.city_a)
        sb = s.city_b if s.cities_are_short else short_city(s.city_b)
        out.append(
            {
                "rank": i,
                "route": s.route,
                "route_key": s.route,
                "route_short": f"{sa}-{sb}",
                "city_a": s.city_a,
                "city_b": s.city_b,
                "flight_nos": sorted(s.flight_nos),
                "flight_no_text": "、".join(sorted(s.flight_nos)),
                "general": round(s.rate("general"), 2),
                "general_ok": s.ok("general"),
                "general_bad": s.bad("general"),
                "arrival": round(s.rate("arrival"), 2),
                "arrival_ok": s.ok("arrival"),
                "arrival_bad": s.bad("arrival"),
                "departure": round(s.rate("departure"), 2),
                "departure_ok": s.ok("departure"),
                "departure_bad": s.bad("departure"),
                "general_total": s.total("general"),
                "arrival_total": s.total("arrival"),
                "departure_total": s.total("departure"),
                "highlight": False,
                "highlight_label": "",
            }
        )
    return out

def _match_city(query: str, full_name: str) -> bool:
    """按调用方文本执行子串匹配；不做城市归并。"""
    if not query or not full_name:
        return False
    return query in full_name or full_name in query

def apply_selected_routes(ranking: list[dict], selected_routes: Iterable[str]) -> list[dict]:
    """Mark rows selected in the result table without changing their ranking."""
    selected = {str(value).strip() for value in selected_routes if str(value).strip()}
    if not selected:
        return ranking
    for row in ranking:
        if row.get("route") in selected or row.get("route_short") in selected:
            row["highlight"] = True
            label = row.get("highlight_label") or ""
            row["highlight_label"] = label or "结果勾选"
    return ranking
