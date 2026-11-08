"""作者：Wangyuan；日期：2026-10-29。离线通用核心，输入由调用方显式提供。"""

from __future__ import annotations

from collections import defaultdict

from typing import Any, Iterable

import datetime as dt

import re

AMBIGUOUS_AIRPORT_CITIES = set()

FIELD_ALIASES = {key: (key,) for key in ("flight_no", "flight_date", "origin", "destination", "std", "sta", "status", "aircraft_type")}

def normalize_airport(value):
    return str(value or "").strip()

MAX_MATCHES = 20_000

class CoflightDataError(ValueError):
    """Raised when supplied flight data cannot support a defensible analysis."""

def _canonical_key(value: Any) -> str:
    return re.sub(r"[\s_\-]+", "", str(value or "").strip()).lower()

def _clean(value: Any) -> str:
    return str(value or "").strip()

def _pick(row: dict[str, Any], aliases: tuple[str, ...], *, preserve_type: bool = False) -> Any:
    lookup = {_canonical_key(key): value for key, value in row.items()}
    for alias in aliases:
        value = lookup.get(_canonical_key(alias))
        if _clean(value):
            return value if preserve_type else _clean(value)
    return ""

def normalize_flight_no(value: Any) -> str:
    return re.sub(r"[^A-Z0-9]", "", _clean(value).upper())

def is_ambiguous_airport_city(value: Any) -> bool:
    text = normalize_airport(value)
    return text in AMBIGUOUS_AIRPORT_CITIES

def _parse_date(value: Any, fallback: dt.date) -> dt.date:
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    text = _clean(value)
    match = re.search(r"(20\d{2})[-/.年](\d{1,2})[-/.月](\d{1,2})", text)
    if match:
        return dt.date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    return fallback

def parse_flight_datetime(value: Any, flight_date: dt.date) -> dt.datetime | None:
    if isinstance(value, dt.datetime):
        return value.astimezone(dt.timezone.utc).replace(tzinfo=None) if value.tzinfo else value
    if isinstance(value, dt.time):
        return dt.datetime.combine(flight_date, value)
    if isinstance(value, (int, float)) and value > 1_000_000_000:
        seconds = float(value) / 1000 if value > 10_000_000_000 else float(value)
        try:
            return dt.datetime.fromtimestamp(seconds, dt.timezone.utc).replace(tzinfo=None)
        except (OverflowError, OSError, ValueError):
            return None
    text = _clean(value)
    if not text:
        return None
    normalized = text.replace("年", "-").replace("月", "-").replace("日", " ").replace("/", "-")
    normalized = normalized.replace("T", " ").strip()
    try:
        parsed = dt.datetime.fromisoformat(normalized.replace("Z", "+00:00"))
        if parsed.tzinfo:
            parsed = parsed.astimezone(dt.timezone.utc).replace(tzinfo=None)
        return parsed
    except ValueError:
        pass
    match = re.search(r"(?:(20\d{2})-(\d{1,2})-(\d{1,2})\s*)?(\d{1,2}):(\d{2})(?::(\d{2}))?", normalized)
    if not match:
        return None
    date_value = flight_date
    if match.group(1):
        date_value = dt.date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    try:
        time_value = dt.time(int(match.group(4)), int(match.group(5)), int(match.group(6) or 0))
    except ValueError:
        return None
    return dt.datetime.combine(date_value, time_value)

def normalize_flights(
    rows: Iterable[dict[str, Any]],
    flight_date: str | dt.date,
    *,
    source: str,
) -> list[dict[str, Any]]:
    fallback_date = dt.date.fromisoformat(flight_date) if isinstance(flight_date, str) else flight_date
    normalized: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str, str, str]] = set()
    for raw in rows:
        if not isinstance(raw, dict):
            continue
        flight_no = normalize_flight_no(_pick(raw, FIELD_ALIASES["flight_no"]))
        origin_value = _pick(raw, FIELD_ALIASES["origin"])
        destination_value = _pick(raw, FIELD_ALIASES["destination"])
        if is_ambiguous_airport_city(origin_value) or is_ambiguous_airport_city(destination_value):
            continue
        origin = normalize_airport(origin_value)
        destination = normalize_airport(destination_value)
        row_date = _parse_date(_pick(raw, FIELD_ALIASES["flight_date"]), fallback_date)
        std_value = _pick(raw, FIELD_ALIASES["std"], preserve_type=True)
        std_dt = parse_flight_datetime(std_value, row_date)
        if not flight_no or not origin or not destination or std_dt is None:
            continue
        sta_value = _pick(raw, FIELD_ALIASES["sta"], preserve_type=True)
        sta_dt = parse_flight_datetime(sta_value, row_date)
        if sta_dt and sta_dt < std_dt - dt.timedelta(hours=12):
            sta_dt += dt.timedelta(days=1)
        item = {
            "flight_no": flight_no,
            "carrier": flight_no[:2],
            "flight_date": row_date.isoformat(),
            "origin": origin,
            "destination": destination,
            "route": f"{origin}-{destination}",
            "std": std_dt.isoformat(timespec="minutes"),
            "std_display": std_dt.strftime("%H:%M"),
            "sta": sta_dt.isoformat(timespec="minutes") if sta_dt else "",
            "sta_display": sta_dt.strftime("%H:%M") if sta_dt else "",
            "status": _pick(raw, FIELD_ALIASES["status"]),
            "aircraft_type": _pick(raw, FIELD_ALIASES["aircraft_type"]),
            "source": source,
        }
        dedupe_key = (
            item["flight_no"], item["flight_date"], item["origin"], item["destination"], item["std"], item["source"]
        )
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        normalized.append(item)
    return normalized

def _is_self_flight(flight_no: str, carrier_prefix: str) -> bool:
    return normalize_flight_no(flight_no).startswith(normalize_flight_no(carrier_prefix))

def _relative_minutes(target_iso: str, candidate_iso: str) -> int:
    target = dt.datetime.fromisoformat(target_iso)
    candidate = dt.datetime.fromisoformat(candidate_iso)
    return round((candidate - target).total_seconds() / 60)

def _window_bucket(delta: int) -> str:
    absolute = abs(delta)
    if absolute <= 60:
        return "1小时核心窗口"
    return "2小时扩展窗口"

def _direction(delta: int) -> str:
    if delta < 0:
        return f"提前 {abs(delta)} 分钟"
    if delta > 0:
        return f"延后 {delta} 分钟"
    return "同时刻"

def analyze_coflights(
    flights: Iterable[dict[str, Any]],
    *,
    carrier_prefix: str,
    window_minutes: int = 120,
    flight_no_filter: str = "",
    origin_filter: str = "",
    destination_filter: str = "",
    query_date: str = "",
    source_status: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if window_minutes not in {60, 120} or not normalize_flight_no(carrier_prefix):
        raise CoflightDataError("时间窗只支持 60 或 120 分钟。")
    materialized = list(flights)
    if not materialized:
        raise CoflightDataError("没有可用于分析的航班数据。")

    if origin_filter and is_ambiguous_airport_city(origin_filter):
        raise CoflightDataError("始发站是多机场城市，请填写具体机场三字码或机场名称。")
    if destination_filter and is_ambiguous_airport_city(destination_filter):
        raise CoflightDataError("到达站是多机场城市，请填写具体机场三字码或机场名称。")

    wanted_flight = normalize_flight_no(flight_no_filter)
    wanted_origin = normalize_airport(origin_filter)
    wanted_destination = normalize_airport(destination_filter)
    targets = []
    for flight in materialized:
        if not _is_self_flight(flight["flight_no"], carrier_prefix):
            continue
        # Adjacent dates may be loaded only to catch competitors around
        # midnight. They must not become extra targets for the selected date.
        if query_date and flight.get("flight_date") != query_date:
            continue
        if wanted_flight and wanted_flight not in flight["flight_no"]:
            continue
        if wanted_origin and wanted_origin not in flight["origin"]:
            continue
        if wanted_destination and wanted_destination not in flight["destination"]:
            continue
        targets.append(dict(flight))
    if not targets:
        raise CoflightDataError("当前数据中没有符合筛选条件的指定前缀的航班。")

    route_index: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for flight in materialized:
        if _is_self_flight(flight["flight_no"], carrier_prefix):
            continue
        route_index[(flight["origin"], flight["destination"])].append(flight)

    matches: list[dict[str, Any]] = []
    target_summaries: list[dict[str, Any]] = []
    seen_matches: set[tuple[str, str, str, str]] = set()
    for target in sorted(targets, key=lambda row: (row["std"], row["flight_no"])):
        one_hour = 0
        two_hour = 0
        target_matches = []
        for candidate in route_index.get((target["origin"], target["destination"]), []):
            delta = _relative_minutes(target["std"], candidate["std"])
            if abs(delta) > window_minutes:
                continue
            key = (target["flight_no"], target["std"], candidate["flight_no"], candidate["std"])
            if key in seen_matches:
                continue
            seen_matches.add(key)
            bucket = _window_bucket(delta)
            match = {
                "target_flight_no": target["flight_no"],
                "target_date": target["flight_date"],
                "route": target["route"],
                "target_std": target["std_display"],
                "coflight_no": candidate["flight_no"],
                "coflight_std": candidate["std_display"],
                "coflight_sta": candidate.get("sta_display", ""),
                "delta_minutes": delta,
                "direction": _direction(delta),
                "window_bucket": bucket,
                "coflight_status": candidate.get("status", ""),
                "aircraft_type": candidate.get("aircraft_type", ""),
                "source": candidate.get("source", ""),
            }
            target_matches.append(match)
            if abs(delta) <= 60:
                one_hour += 1
            else:
                two_hour += 1
            if len(matches) + len(target_matches) > MAX_MATCHES:
                raise CoflightDataError(f"匹配结果超过 {MAX_MATCHES} 条，请增加航班号或机场筛选条件。")
        target_matches.sort(key=lambda row: (abs(row["delta_minutes"]), row["delta_minutes"], row["coflight_no"]))
        matches.extend(target_matches)
        target_summaries.append({
            **target,
            "competition_count_1h": one_hour,
            "competition_count_2h_extra": two_hour,
            "competition_count_total": one_hour + two_hour,
            "assessment": "发现共飞" if one_hour + two_hour else "本次范围未发现共飞",
        })

    matched_targets = sum(item["competition_count_total"] > 0 for item in target_summaries)
    unique_competitors = len({(row["coflight_no"], row["coflight_std"], row["route"]) for row in matches})
    return {
        "version": "2.0",
        "query": {
            "flight_date": query_date or targets[0]["flight_date"],
            "carrier_prefix": normalize_flight_no(carrier_prefix),
            "window_minutes": window_minutes,
            "flight_no": wanted_flight,
            "origin": wanted_origin,
            "destination": wanted_destination,
        },
        "summary": {
            "source_flights": len(materialized),
            "target_flights": len(target_summaries),
            "targets_with_coflight": matched_targets,
            "unique_coflights": unique_competitors,
            "matches": len(matches),
        },
        "targets": target_summaries,
        "matches": matches,
        "source_status": source_status or [],
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
    }
