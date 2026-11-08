"""作者：Wangyuan；日期：2026-10-29。离线通用核心，输入由调用方显式提供。"""

from __future__ import annotations

from collections import Counter

from dataclasses import dataclass, replace

from datetime import date, datetime, timedelta

from typing import Optional

import re

COORDINATOR_ALIASES = {}

NAME_BLOCK_WORDS = set()

ROLE_WORDS = []

DATE_PATTERNS = [
    re.compile(r"(?<!\d)(?P<y>\d{4,})[年\-/\.](?P<m>\d+)[月\-/\.](?P<d>\d+)(?!\d)"),
    re.compile(r"(?<!\d)(?P<m>\d+)月(?P<d>\d+)日?(?!\d)"),
    # 数字短日期只认标题、行首或显式日期标签，正文小数和机型斜杠不是日期。
    re.compile(
        r"(?:^\s*[【\[(（]?\s*|(?:业务日期|日期)\s*[:：]\s*)"
        r"(?P<m>\d+)[\-/\.](?P<d>\d+)(?=\s|$|[日)\]】），,])",
        re.MULTILINE,
    ),
]

FLIGHT_PATTERN = re.compile(r"\b[A-Z0-9]{2,3}\d{3,4}(?:/[A-Z0-9\-]+\))?")

TIME_PATTERN = re.compile(r"(?<!\d)([01]?\d|2[0-3]):([0-5]\d)(?!\d)")

COORD_PATTERN = re.compile(r"经\s*([^。\.；;]{1,80}?)\s*协调")

COORD_NEAR_PATTERN = re.compile(
    r"原预起(?:时间)?[^\n]{0,160}?经\s*((?:(?!协调).){1,80}?)\s*协调[^\n]{0,60}?实飞"
)

COORD_SPLIT_PATTERN = re.compile(r"及|和|与|以及|并|,|，|、|/|／|;|；")

@dataclass
class ParsedRecord:
    flight_date: date
    flight_no: str
    std: str
    atd: str
    advance_hhmm: str
    advance_minutes: int
    coordinator: str
    raw_text: str
    std_date: Optional[date] = None
    atd_date: Optional[date] = None

def normalize_time(text: str) -> Optional[str]:
    m = TIME_PATTERN.fullmatch(text.strip())
    if not m:
        return None
    return f"{int(m.group(1)):02d}:{int(m.group(2)):02d}"

def minutes_of_hhmm(hhmm: str) -> int:
    hh, mm = hhmm.split(":")
    return int(hh) * 60 + int(mm)

def diff_minutes(
    std_hhmm: str, atd_hhmm: str, *,
    std_date: Optional[date] = None, atd_date: Optional[date] = None,
) -> int:
    """计算真实提前分钟；两端日期不齐或大时差无日期时拒绝猜测跨日。"""
    if normalize_time(std_hhmm) is None or normalize_time(atd_hhmm) is None:
        raise ValueError("时刻不合法，须为00:00至23:59")
    if (std_date is None) != (atd_date is None):
        raise ValueError("原预起与实飞日期必须同时明确")
    if std_date is not None and atd_date is not None:
        planned = datetime.combine(std_date, datetime.strptime(std_hhmm, "%H:%M").time())
        actual = datetime.combine(atd_date, datetime.strptime(atd_hhmm, "%H:%M").time())
        return int((planned - actual).total_seconds() // 60)
    raw = minutes_of_hhmm(std_hhmm) - minutes_of_hhmm(atd_hhmm)
    if abs(raw) >= 720:
        raise ValueError("时差达到12小时，须明确原预起与实飞的完整日期，不能推测跨日")
    return raw

def fmt_diff_hhmm(minutes: int) -> str:
    sign = "-" if minutes < 0 else ""
    abs_min = abs(minutes)
    return f"{sign}{abs_min // 60:02d}:{abs_min % 60:02d}"

def normalize_coordinator_token(token: str) -> Optional[str]:
    t = str(token).strip().strip("，,。.;；:：()（）[]【】 ")
    if not t:
        return None
    t = re.sub(r"\s+", "", t)
    raw = t
    if t in {"签派", "助理签派席"}:
        return t
    for word in ROLE_WORDS:
        t = t.replace(word, "")
    t = t.strip()
    if t.startswith("部") and len(t) >= 3:
        t = t[1:]
    if t.endswith("总") and len(t) >= 3:
        t = t[:-1]

    name_candidates = re.findall(r"[\u4e00-\u9fff]{2,4}", t)
    valid_candidates = []
    for cand in name_candidates:
        if any(b in cand for b in NAME_BLOCK_WORDS):
            continue
        valid_candidates.append(cand)
    if valid_candidates:
        return COORDINATOR_ALIASES.get(valid_candidates[-1], valid_candidates[-1])

    if "签派" in raw:
        return "签派"
    return None

def extract_coordinator_names(text: str, fallback: str = "") -> list[str]:
    segments: list[str] = []
    near_match = COORD_NEAR_PATTERN.search(text)
    if near_match:
        segments.append(near_match.group(1))
    segments.extend(COORD_PATTERN.findall(text))
    if fallback:
        segments.append(fallback)

    names: list[str] = []
    for seg in segments:
        for part in COORD_SPLIT_PATTERN.split(str(seg)):
            name = normalize_coordinator_token(part)
            if name and name not in names:
                names.append(name)

    if not names and "签派" in text:
        names.append("签派")
    return names

def build_coordinator_report(records: list["ParsedRecord"]) -> dict[str, object]:
    total_flights = len(records)
    count_by_name: Counter[str] = Counter()
    normal_by_name: Counter[str] = Counter()
    minutes_by_name: Counter[str] = Counter()
    multi_coordinator_flights = 0

    for rec in records:
        names = extract_coordinator_names(rec.raw_text, rec.coordinator)
        unique_names = list(dict.fromkeys(names))
        if len(unique_names) >= 2:
            multi_coordinator_flights += 1
        is_normal = "航班起飞正常" in rec.raw_text
        for name in unique_names:
            count_by_name[name] += 1
            minutes_by_name[name] += rec.advance_minutes
            if is_normal:
                normal_by_name[name] += 1

    rows: list[dict[str, object]] = []
    for name, cnt in count_by_name.items():
        normal_cnt = normal_by_name.get(name, 0)
        adv_min = minutes_by_name.get(name, 0)
        share = (cnt / total_flights * 100.0) if total_flights > 0 else 0.0
        normal_rate = (normal_cnt / cnt * 100.0) if cnt > 0 else 0.0
        rows.append(
            {
                "name": name,
                "count": cnt,
                "share": share,
                "normal_count": normal_cnt,
                "normal_rate": normal_rate,
                "advance_minutes": adv_min,
                "advance_hhmm": fmt_diff_hhmm(adv_min),
            }
        )

    rows.sort(key=lambda x: (-int(x["count"]), -int(x["advance_minutes"]), str(x["name"])))

    lines = [
        f"协调人统计：共识别{len(rows)}位协调人，涉及多人协同航班{multi_coordinator_flights}班。"
    ]
    for idx, row in enumerate(rows, start=1):
        lines.append(
            f"{idx}. {row['name']}：协调{row['count']}班（占比{row['share']:.2f}%），"
            f"起飞正常{row['normal_count']}班，正常率{row['normal_rate']:.2f}%，"
            f"累计时间提前{row['advance_hhmm']}（{row['advance_minutes']}分钟）。"
        )

    return {
        "unique_count": len(rows),
        "multi_coordinator_flights": multi_coordinator_flights,
        "rows": rows,
        "report_text": "\n".join(lines),
    }

def prev_month_year(ref_date: Optional[date] = None) -> tuple[int, int]:
    d = ref_date or datetime.now().date()
    if d.month == 1:
        return d.year - 1, 12
    return d.year, d.month - 1

def build_monthly_summary(
    records: list["ParsedRecord"],
    total_flights: Optional[int],
    ref_date: date,
    *, hourly_cost: float,
) -> dict[str, object]:
    """生成统计主句；未知分母不等同零关联折算，费用仅为既有单价折算。"""
    coord_count = len(records)
    total_advance_minutes = sum(item.advance_minutes for item in records)
    total_advance_hhmm = fmt_diff_hhmm(total_advance_minutes)
    reduction_minutes = max(total_advance_minutes, 0)
    reduction_hours = reduction_minutes // 60
    reduction_min_part = reduction_minutes % 60
    apu_cost = (reduction_minutes / 60.0) * hourly_cost
    normal_takeoff_count = sum(1 for item in records if "航班起飞正常" in item.raw_text)
    denominator_valid = type(total_flights) is int and total_flights > 0
    total_flights_safe = total_flights if denominator_valid else None
    ontime_rate = (normal_takeoff_count / total_flights * 100.0) if denominator_valid else None
    improvement_text = (
        f"按全月计划折算起飞正常率关联折算{ontime_rate:.2f}个百分点"
        if ontime_rate is not None else "全月计划分母待核验，关联折算百分点暂不计算"
    )
    _, month = prev_month_year(ref_date)

    text = (
        f"{month}月协调数据汇总："
        f"{month}月共协调{coord_count}班，"
        f"记录时刻提前{reduction_hours}小时{reduction_min_part:02d}分钟，"
        f"按{hourly_cost:g}元/小时折算APU等待费用{apu_cost:.1f}元（非实测收益）；"
        f"协调起飞正常{normal_takeoff_count}班，"
        f"{improvement_text}。"
    )

    return {
        "month": month,
        "total_flights": total_flights_safe,
        "coord_count": coord_count,
        "total_advance_minutes": total_advance_minutes,
        "total_advance_hhmm": total_advance_hhmm,
        "reduction_hours": reduction_hours,
        "reduction_minutes_part": reduction_min_part,
        "apu_cost": round(apu_cost, 1),
        "normal_takeoff_count": normal_takeoff_count,
        "ontime_rate": ontime_rate,
        "summary_text": text,
        "quality_status": "available" if denominator_valid else "partial",
        "missing_inputs": [] if denominator_valid else ["缺少有效的全月计划航班分母"],
    }

_TIME_LABEL = re.compile(r"原预起(?:时间)?|实飞")

_TIME_SEGMENT = re.compile(r"(?:原预起(?:时间)?|实飞)\s*[:：]?[^，,。；;\n]*")

_FULL_FIELD_DATE = re.compile(r"(?P<y>\d{4,})[年\-/\.](?P<m>\d+)[月\-/\.](?P<d>\d+)日?")

_RELATIVE_DAYS = {"当日": 0, "同日": 0, "次日": 1, "翌日": 1}

_DATE_WORDS = re.compile(r"当日|同日|当天|当晚|当夜|(?:次|翌|明|后|隔)(?:日|天|晨|早|晚|夜)|跨日|跨夜|跨午夜|昨日|前日|前一天|后一天|第二天|第二日|下一天|\bD\s*\+\s*\d+(?!\d)|[+-]\s*\d+\s*天", re.IGNORECASE)

_ZONE_WORDS = re.compile(r"UTC|GMT|世界时|祖鲁时|当地时间|(?<!\d)\d{1,2}:\d{2}\s*Z\b|(?<![A-Za-z0-9])Z(?=\s*\d{1,2}:)", re.IGNORECASE)

@dataclass(frozen=True)
class _DepartureTiming:
    """只保存本次由原文和业务日期解析的时刻日期证据。"""
    std: str
    atd: str
    std_date: date
    atd_date: date
    minutes: int
    explicit_dates: bool

def _business_date_text(text: str) -> str:
    """屏蔽时刻字段局部日期，防业务日被原预起/实飞的日期覆盖。"""
    return _TIME_SEGMENT.sub(lambda match: " " * len(match.group(0)), text)

def _field_date(token: str, business_date: date) -> date:
    """只接受完整公历日期或相对已知业务日的明确日期词，不猜字段年份。"""
    token = token.strip().strip("（）() ")
    if token in _RELATIVE_DAYS:
        try:
            return business_date + timedelta(days=_RELATIVE_DAYS[token])
        except OverflowError as exc:
            raise ValueError("相对日期超出可表示范围") from exc
    match = _FULL_FIELD_DATE.fullmatch(token)
    if not match:
        raise ValueError(f"时刻字段日期表达未能核验：{token}；须完整年月日或当日/同日/次日/翌日")
    try:
        return date(int(match.group("y")), int(match.group("m")), int(match.group("d")))
    except ValueError as exc:
        raise ValueError(f"时刻字段日期不合法：{token}") from exc

def _field_value(body: str, business_date: date, label: str) -> tuple[str, Optional[date]]:
    """读取字段前置日期或时刻后括号日期；不从无关正文猜日期归属。"""
    body = body.strip().lstrip(":：").strip()
    clock = re.search(r"(?<!\d)(\d{1,2}:\d{2})(?!\d)", body)
    if not clock:
        raise ValueError(f"{label}时刻缺失或格式不合法")
    value = normalize_time(clock.group(1))
    if value is None:
        raise ValueError(f"{label}时刻不合法：{clock.group(1)}")
    prefix = body[:clock.start()].strip().strip("（）() ")
    result_date = _field_date(prefix, business_date) if prefix else None
    suffix = body[clock.end():].strip()
    if re.match(r"[+-]\s*\d", suffix):
        raise ValueError(f"{label}含未支持的时区偏移，不能猜测转换")
    # 兼容原有单纯括号包裹时刻，如原预起(09:00)，但不忽略日期声明。
    suffix = suffix.lstrip(")）").strip()
    bracket = re.match(r"[（(]([^）)]*)[）)]", suffix)
    if bracket:
        token = bracket.group(1).strip()
        if (_DATE_WORDS.search(token) or any(p.search(token) for p in DATE_PATTERNS)
                or re.fullmatch(r"(?:D\s*)?[+-]\s*\d+", token, re.IGNORECASE)):
            trailing_date = _field_date(token, business_date)
            if result_date is not None and result_date != trailing_date:
                raise ValueError(f"{label}前后日期声明矛盾")
            result_date = trailing_date
            suffix = suffix[bracket.end():]
    if _DATE_WORDS.search(suffix) or any(p.search(suffix) for p in DATE_PATTERNS):
        raise ValueError(f"{label}存在未能绑定的日期声明；日期须紧邻字段前或时刻后括号")
    return value, result_date

def _departure_timing(
    text: str, business_date: Optional[date],
    fallback: Optional[tuple[str, str]] = None,
) -> _DepartureTiming:
    """两端日期有声明即须均明确；旧结构化记录也不得用缓存分钟跳过核验。"""
    if business_date is None:
        raise ValueError("业务日期未明确，不能解释时刻所属日期")
    if _ZONE_WORDS.search(text):
        raise ValueError("存在未支持的时区声明，不能推测UTC与本地时间转换")
    labels = list(_TIME_LABEL.finditer(text))
    std_value: Optional[tuple[str, Optional[date]]] = None
    atd_value: Optional[tuple[str, Optional[date]]] = None
    for index, label in enumerate(labels):
        end = labels[index + 1].start() if index + 1 < len(labels) else len(text)
        body = re.split(r"[，,。；;\n]", text[label.end():end], maxsplit=1)[0]
        value = _field_value(body, business_date, label.group(0))
        if label.group(0).startswith("原预起"):
            if std_value is not None:
                raise ValueError("原预起字段出现多个版本，须人工确认")
            std_value = value
        else:
            if atd_value is not None:
                raise ValueError("实飞字段出现多个版本，须人工确认")
            atd_value = value
    if not labels and fallback is not None:
        # 截图复核结构化表允许普通同日时刻；存在跨日用语或大时差仍须原文日期证据。
        std_value, atd_value = (fallback[0], None), (fallback[1], None)
    if std_value is None or atd_value is None:
        raise ValueError("原预起或实飞时刻字段不完整")
    std, planned_date = std_value
    atd, actual_date = atd_value
    outside_declaration = _DATE_WORDS.search(_business_date_text(text))
    if outside_declaration:
        raise ValueError("存在未能绑定到两时刻的跨日/相对日期声明")
    explicit_dates = planned_date is not None or actual_date is not None
    if explicit_dates:
        if planned_date is None or actual_date is None:
            raise ValueError("存在时刻日期声明，但原预起与实飞两端日期未同时明确")
        minutes = diff_minutes(std, atd, std_date=planned_date, atd_date=actual_date)
    else:
        minutes = diff_minutes(std, atd)
        planned_date = actual_date = business_date
    return _DepartureTiming(std, atd, planned_date, actual_date, minutes, explicit_dates)

def has_date_marker(text: str) -> bool:
    """识别显式日期标记，供入口区分缺日期与无效日期，禁止回落旧日期。"""
    return any(pattern.search(_business_date_text(text)) for pattern in DATE_PATTERNS)

def extract_date_from_text(
    text: str,
    default_year: int,
    current_date: Optional[date],
) -> Optional[date]:
    """解析真实公历日期；显式无效日期返回空，调用方须另查标记。"""
    for idx, pat in enumerate(DATE_PATTERNS):
        m = pat.search(_business_date_text(text))
        if not m:
            continue
        try:
            if idx == 0:
                return date(int(m.group("y")), int(m.group("m")), int(m.group("d")))
            year = current_date.year if current_date else default_year
            return date(year, int(m.group("m")), int(m.group("d")))
        except ValueError:
            return None
    return None

def clean_chat_prefix(text: str) -> str:
    # Remove common prefixes from chat exports: [10:32]张三: ...
    t = text.strip()
    t = re.sub(r"^\[[^\]]{1,30}\]\s*", "", t)
    t = re.sub(r"^[^:：]{1,20}[:：]\s*(?=[A-Z0-9]{2,3}\d{3,4})", "", t)
    return t.strip()

def parse_record(line: str, line_date: Optional[date], strict: bool = False) -> Optional[ParsedRecord]:
    """提取单条消息；行内日期冲突或无效时拒绝，不用外部日期掩盖错误。"""
    if not line_date:
        return None

    if has_date_marker(line):
        explicit_date = extract_date_from_text(line, line_date.year, line_date)
        if explicit_date is None or explicit_date != line_date:
            return None
    text = clean_chat_prefix(line)
    if "航班起飞正常" in text and "航班起飞延误" in text:
        return None
    if "原预起" not in text or "实飞" not in text:
        return None

    flight_match = FLIGHT_PATTERN.search(text)
    if not flight_match:
        return None
    try:
        timing = _departure_timing(text, line_date)
    except (ValueError, OverflowError):
        return None
    std, atd, adv_min = timing.std, timing.atd, timing.minutes
    names = extract_coordinator_names(text)
    coordinator = "、".join(names)
    if strict and not coordinator:
        return None

    return ParsedRecord(
        flight_date=line_date,
        flight_no=flight_match.group(0),
        std=std,
        atd=atd,
        advance_hhmm=fmt_diff_hhmm(adv_min),
        advance_minutes=adv_min,
        coordinator=coordinator,
        raw_text=text,
        std_date=timing.std_date,
        atd_date=timing.atd_date,
    )

def reconcile_records(
    records: list[ParsedRecord], pending: Optional[list[str]] = None, *,
    require_business_date_evidence: bool = False,
) -> tuple[list[ParsedRecord], list[str]]:
    """按日期和航班去重；业务字段冲突整组隔离，避免首条胜出或重复计数。

    对语义等同副本保留字典序最小原文，保证重排输入不会改变核验结果。
    冲突字段覆盖时刻、协调人集合、状态及计算字段；输出保留每个不同原文。
    pending须来自本解析器保留的待确认列表；仅本函数的稳定冲突标记继续
    阻断跨批次同业务键，普通无效原文不阻断其他合法记录。调用方合并原pending。
    归档导出须开启require_business_date_evidence：时刻带日期声明时，缓存业务日
    必须另有原文业务日期佐证，不能以消息发送日替代；普通同日旧记录保持兼容。
    """
    blocked: set[tuple[date, str]] = set()
    conflict_marker = re.compile(r"^冲突重复待确认：(\d{4}-\d{2}-\d{2})/([A-Z0-9]{2,3}\d{3,4})；")
    for issue in pending or []:
        match = conflict_marker.match(issue)
        if match:
            try:
                blocked.add((date.fromisoformat(match.group(1)), match.group(2)))
            except ValueError:
                continue
    grouped: dict[tuple[date, str], list[ParsedRecord]] = {}
    valid: list[ParsedRecord] = []
    conflicts: list[str] = []
    for rec in records:
        match = re.match(r"[A-Z0-9]{2,3}\d{3,4}", rec.flight_no)
        key = (rec.flight_date, match.group(0) if match else rec.flight_no)
        try:
            if has_date_marker(rec.raw_text):
                raw_business_date = extract_date_from_text(rec.raw_text, rec.flight_date.year, rec.flight_date)
                if raw_business_date is None or raw_business_date != rec.flight_date:
                    raise ValueError("原文业务日期无效或与存档业务日期不一致")
            timing = _departure_timing(rec.raw_text, rec.flight_date, (rec.std, rec.atd))
            if (require_business_date_evidence and timing.explicit_dates
                    and not has_date_marker(rec.raw_text)):
                raise ValueError("归档业务日期缺少原文证据，不能用缓存/发送日解释日期")
            if timing.std != rec.std or timing.atd != rec.atd:
                raise ValueError("存档时刻与原文字段不一致")
            if timing.minutes != rec.advance_minutes or fmt_diff_hhmm(timing.minutes) != rec.advance_hhmm:
                raise ValueError("存档提前分钟/时长与真实日期重算不一致")
        except (ValueError, OverflowError) as exc:
            conflicts.append(f"时刻日期待确认：{key[0].isoformat()}/{key[1]}；{exc}；原文：{rec.raw_text}")
            continue
        # 只补本次核验的日期元数据；不信任旧对象或DB可能保存的日期属性。
        checked = replace(rec, std_date=timing.std_date, atd_date=timing.atd_date)
        grouped.setdefault(key, []).append(checked)
    for key in sorted(grouped):
        group = grouped[key]
        if key in blocked:
            for raw in sorted({r.raw_text for r in group}):
                conflicts.append(
                    f"冲突重复待确认：{key[0].isoformat()}/{key[1]}；"
                    f"既有批次存在未解决冲突，本版本不得单独计入；原文：{raw}"
                )
            continue
        fields = {
            "原预起": {r.std for r in group},
            "实飞": {r.atd for r in group},
            "原预起日期": {r.std_date for r in group},
            "实飞日期": {r.atd_date for r in group},
            "协调人": {tuple(sorted(extract_coordinator_names(r.raw_text, r.coordinator))) for r in group},
            "起飞状态": {("航班起飞正常" in r.raw_text, "航班起飞延误" in r.raw_text) for r in group},
            "提前分钟": {r.advance_minutes for r in group},
            "提前时长": {r.advance_hhmm for r in group},
        }
        different = [name for name, values in fields.items() if len(values) > 1]
        if different:
            for raw in sorted({r.raw_text for r in group}):
                conflicts.append(f"冲突重复待确认：{key[0].isoformat()}/{key[1]}；冲突字段：{'、'.join(different)}；原文：{raw}")
        else:
            valid.append(min(group, key=lambda r: (r.raw_text, r.flight_no, r.coordinator)))
    return valid, conflicts
