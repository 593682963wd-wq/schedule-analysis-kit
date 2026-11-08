"""作者：Wangyuan；日期：2026-10-29。离线通用核心，输入由调用方显式提供。"""

from __future__ import annotations

from copy import deepcopy

from dataclasses import dataclass

from datetime import datetime

from decimal import Decimal, ROUND_HALF_UP

from difflib import SequenceMatcher

from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

from openpyxl.utils import get_column_letter

import math

import re

NAME_ALIASES = {}

def airline_row_fill(name):
    return None

def default_airlines(store):
    return list(dict.fromkeys(str(x) for x in store["entities"]))

def historical_warnings(store, year, month, name, plan, reason):
    return []

@dataclass
class Issue:
    level: str
    message: str
    row_name: str | None = None

    def as_dict(self) -> dict:
        return {
            "level": self.level,
            "message": self.message,
            "row_name": self.row_name,
        }

def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def stats_range_text(year: int, last_month: int) -> str:
    safe_month = max(1, int(last_month))
    if safe_month == 1:
        return f"{year}年1月"
    return f"{year}年1至{safe_month}月"

def stats_cutoff_text(year: int, last_month: int) -> str:
    safe_month = max(1, int(last_month))
    return f"统计截止{year}年{safe_month}月"

def export_workbook_title(year: int, last_month: int) -> str:
    return f"{stats_range_text(year, last_month)}项目目标事件占比排名（{stats_cutoff_text(year, last_month)}）"

def round_percent(value: float) -> Decimal:
    return (Decimal(str(value)) * Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

def parse_percent_text(text: str | None) -> float | None:
    if not text:
        return None
    cleaned = text.strip().replace("％", "%")
    if not re.fullmatch(r"\d+(?:\.\d+)?%", cleaned):
        return None
    return float(cleaned.rstrip("%"))

def display_width(value) -> int:
    text = "" if value is None else str(value)
    width = 0
    for char in text:
        width += 2 if ord(char) > 127 else 1
    return width

def year_store(store: dict, year: int) -> dict:
    years = store.setdefault("years", {})
    year_data = years.setdefault(str(year), {"months": {}, "updated_at": now_text()})
    year_data.setdefault("months", {})
    return year_data

def normalize_name(text: str) -> str:
    return re.sub(r"[\s\-—_·•.,，。:：;；()（）]", "", text or "")

def best_name_match(raw_name: str, canonical_names: list[str]) -> tuple[str, float]:
    raw_name = (raw_name or "").strip()
    if not raw_name:
        return "", 0.0
    if raw_name in NAME_ALIASES:
        mapped = NAME_ALIASES[raw_name]
        return mapped, 1.0
    if raw_name in canonical_names:
        return raw_name, 1.0

    raw_norm = normalize_name(raw_name)
    best_name = raw_name
    best_score = 0.0
    for candidate in canonical_names:
        cand_norm = normalize_name(candidate)
        score = SequenceMatcher(None, raw_norm, cand_norm).ratio()
        if score > best_score:
            best_name = candidate
            best_score = score
    return best_name, best_score

def parse_row_from_tokens(row_index: int, tokens: list[dict]) -> dict:
    row = {
        "rank": row_index + 1,
        "name_raw": "",
        "plan": None,
        "reason": None,
        "pct_irregular_text": "",
        "pct_plan_text": "",
        "field_sources": {},
    }

    col_tokens: dict[int, list[str]] = {}
    for token in tokens:
        col_tokens.setdefault(token["col"], []).append(token["text"])

    if col_tokens.get(0):
        serial = re.search(r"\d{1,2}", " ".join(col_tokens[0]))
        if serial:
            row["rank"] = int(serial.group())
            row["field_sources"]["rank"] = "ocr"
    else:
        row["field_sources"]["rank"] = "row_order"

    if col_tokens.get(1):
        row["name_raw"] = "".join(col_tokens[1]).replace(" ", "")
        row["field_sources"]["name"] = "ocr"
    if col_tokens.get(2):
        match = re.search(r"\d+", "".join(col_tokens[2]))
        if match:
            row["plan"] = int(match.group())
            row["field_sources"]["plan"] = "ocr"
    if col_tokens.get(3):
        match = re.search(r"\d+", "".join(col_tokens[3]))
        if match:
            row["reason"] = int(match.group())
            row["field_sources"]["reason"] = "ocr"
    if col_tokens.get(4):
        match = re.search(r"\d+(?:\.\d+)?%", "".join(col_tokens[4]).replace("％", "%"))
        if match:
            row["pct_irregular_text"] = match.group()
            row["field_sources"]["pct_irregular"] = "ocr"
    if col_tokens.get(5):
        match = re.search(r"\d+(?:\.\d+)?%", "".join(col_tokens[5]).replace("％", "%"))
        if match:
            row["pct_plan_text"] = match.group()
            row["field_sources"]["pct_plan"] = "ocr"

    return row

def infer_reason(plan: int | None, pct_plan_text: str) -> int | None:
    pct_value = parse_percent_text(pct_plan_text)
    if plan is None or plan <= 0 or pct_value is None:
        return None
    matched: list[int] = []
    for candidate in range(0, min(plan, max(plan, 1)) + 1):
        ratio = float(round_percent(candidate / plan))
        if abs(ratio - pct_value) < 0.0001:
            matched.append(candidate)
    if not matched:
        return None
    target = plan * pct_value / 100
    return matched[0] if len(matched) == 1 else None

def infer_plan(reason: int | None, pct_plan_text: str) -> int | None:
    pct_value = parse_percent_text(pct_plan_text)
    if reason is None or reason <= 0 or pct_value is None or pct_value <= 0:
        return None

    rough = max(reason, int(round(reason * 100 / pct_value)))
    candidates: list[int] = []
    start = max(1, reason, rough - 400)
    end = rough + 400
    for plan in range(start, end + 1):
        ratio = float(round_percent(reason / plan))
        if abs(ratio - pct_value) < 0.0001:
            candidates.append(plan)
    if not candidates:
        return None
    return candidates[0] if len(candidates) == 1 else None

def validate_rows(
    rows: list[dict],
    total_row: dict,
    year: int,
    month: int,
    store: dict,
    expected_row_count: int | None = None,
) -> tuple[list[dict], list[dict]]:
    issues: list[Issue] = []
    canonical_names = default_airlines(store)
    seen_names: set[str] = set()
    computed_rows: list[dict] = []

    for index, row in enumerate(rows, start=1):
        row_copy = deepcopy(row)
        row_issues: list[str] = []
        raw_name = row_copy.get("name") or row_copy.get("name_raw", "")
        matched_name, score = best_name_match(raw_name, canonical_names)
        row_copy["name"] = matched_name or raw_name
        row_copy["name_match_score"] = round(score, 4)

        if raw_name and matched_name != raw_name:
            row_issues.append(f"项目名称自动修正为“{matched_name}”")
        if score < 0.68:
            row_issues.append("项目名称匹配置信度较低")

        if row_copy.get("reason") is None:
            inferred = infer_reason(row_copy.get("plan"), row_copy.get("pct_plan_text", ""))
            if inferred is not None:
                row_copy["reason"] = inferred
                row_copy.setdefault("field_sources", {})["reason"] = "inferred_from_pct_plan"
                row_issues.append("目标事件班数由占计划比例反推")

        if row_copy.get("plan") is None:
            inferred = infer_plan(row_copy.get("reason"), row_copy.get("pct_plan_text", ""))
            if inferred is not None:
                row_copy["plan"] = inferred
                row_copy.setdefault("field_sources", {})["plan"] = "inferred_from_pct_plan"
                row_issues.append("计划班次由占计划比例反推")

        if not row_copy.get("name"):
            row_issues.append("缺少项目名称")
        if row_copy.get("plan") is None:
            row_issues.append("缺少计划班次")
        elif type(row_copy["plan"]) is not int or row_copy["plan"] <= 0:
            row_issues.append("计划数必须为正")
        if row_copy.get("reason") is None:
            row_issues.append("缺少目标事件班数")

        plan = row_copy.get("plan")
        reason = row_copy.get("reason")
        if reason is not None and (type(reason) is not int or reason < 0):
            row_issues.append("目标事件班数必须为非负整数")
        elif type(reason) is int and type(plan) is int and reason > plan:
            row_issues.append("目标事件班数不能大于计划班次")
        if type(plan) is int and type(reason) is int and plan > 0 and 0 <= reason <= plan:
            computed_pct_plan = float(round_percent(reason / plan))
            row_copy["pct_plan_computed"] = computed_pct_plan
            if row_copy.get("pct_plan_text"):
                stated = parse_percent_text(row_copy["pct_plan_text"])
                if stated is not None and abs(stated - computed_pct_plan) > 0.011:
                    row_issues.append(
                        f"占计划比例与班数重算不一致，按文件值保留（文件值 {row_copy['pct_plan_text']}，重算值 {computed_pct_plan:.2f}%）"
                    )
            row_copy["historical_warnings"] = historical_warnings(store, year, month, row_copy["name"], plan, reason)
            row_issues.extend(row_copy["historical_warnings"])

        if row_copy["name"] in seen_names:
            row_issues.append("项目名称重复")
        elif row_copy.get("name"):
            seen_names.add(row_copy["name"])

        row_copy["review_issues"] = row_issues
        computed_rows.append(row_copy)

    target_row_count = expected_row_count if expected_row_count is not None else len(canonical_names)
    if len(computed_rows) != target_row_count:
        issues.append(Issue("warning", f"识别到 {len(computed_rows)} 行项目数据，预期应为 {target_row_count} 行。"))

    valid_counts = [row for row in computed_rows if type(row.get('plan')) is int and type(row.get('reason')) is int and row['plan'] > 0 and 0 <= row['reason'] <= row['plan']]
    total_plan = sum(row['plan'] for row in valid_counts)
    total_reason = sum(row['reason'] for row in valid_counts)
    total_pct_plan = float(round_percent(total_reason / total_plan)) if total_plan else 0.0

    total_copy = deepcopy(total_row)
    total_copy["plan_computed"] = total_plan
    total_copy["reason_computed"] = total_reason
    total_copy["pct_plan_computed"] = total_pct_plan
    total_copy["review_issues"] = []

    if total_row.get("plan") is not None and total_plan != int(total_row["plan"]):
        issues.append(Issue("warning", f"合计计划班次不一致，按文件值保留（文件值 {total_row['plan']}，重算 {total_plan}）。"))
    if total_row.get("reason") is not None and total_reason != int(total_row["reason"]):
        issues.append(Issue("warning", f"合计目标事件班数不一致，按文件值保留（文件值 {total_row['reason']}，重算 {total_reason}）。"))

    stated_total_pct = parse_percent_text(total_row.get("pct_plan_text", ""))
    if stated_total_pct is not None and abs(stated_total_pct - total_pct_plan) > 0.011:
        issues.append(
            Issue(
                "warning",
                f"合计占计划比例与班数重算不一致，按文件值保留（文件值 {total_row['pct_plan_text']}，重算值 {total_pct_plan:.2f}%）。",
            )
        )

    sortable_rows = [row for row in computed_rows if row.get("plan") and row.get("reason") is not None]
    sorted_names = [
        row["name"]
        for row in sorted(
            sortable_rows,
            key=lambda item: (
                item.get("pct_plan_computed", math.inf),
                item.get("reason", math.inf),
                item.get("name", ""),
            ),
        )
    ]
    original_names = [row.get("name") for row in computed_rows]
    if original_names[: len(sorted_names)] != sorted_names:
        issues.append(Issue("warning", "按重算占计划比例排序后，行顺序与原表不完全一致。"))

    for row in computed_rows:
        for message in row.get("review_issues", []):
            issues.append(Issue("warning", message, row.get("name")))

    return computed_rows, [issue.as_dict() for issue in issues]

def build_year_rows(store: dict, year: int) -> tuple[list[int], list[dict], dict, dict[int, dict[str, int]]]:
    year_data = year_store(store, year)
    months_present = sorted(int(key) for key in year_data.get("months", {}).keys())
    if not months_present:
        raise ValueError(f"{year} 年还没有导入任何月份数据。")

    month_range = list(range(1, max(months_present) + 1))
    if months_present != month_range:
        raise ValueError("年度累计要求起始月至截止月连续，缺失月份不能当零")
    airlines = default_airlines(store)
    monthly_map: dict[int, dict[str, dict]] = {}
    month_totals_map: dict[int, dict[str, int]] = {}
    for month in month_range:
        month_data = year_data.get("months", {}).get(str(month), {})
        monthly_map[month] = {row["name"]: row for row in month_data.get("rows", [])}
        stored_totals = month_data.get("totals", {})
        computed_plan = sum(int(row.get("plan") or 0) for row in month_data.get("rows", []))
        computed_reason = sum(int(row.get("reason") or 0) for row in month_data.get("rows", []))
        month_totals_map[month] = {
            "plan": int(stored_totals.get("plan", computed_plan)),
            "reason": int(stored_totals.get("reason", computed_reason)),
        }

    rows = []
    for airline in airlines:
        monthly_cells = {}
        total_plan = 0
        total_reason = 0
        for month in month_range:
            source_row = monthly_map[month].get(airline)
            if source_row:
                plan = int(source_row["plan"])
                reason = int(source_row["reason"])
            else:
                plan = 0
                reason = 0
            monthly_cells[month] = {"plan": plan, "reason": reason}
            total_plan += plan
            total_reason += reason
        if total_plan == 0 and total_reason == 0:
            continue
        ratio = total_reason / total_plan if total_plan else math.inf
        rows.append(
            {
                "name": airline,
                "months": monthly_cells,
                "total_plan": total_plan,
                "total_reason": total_reason,
                "total_ratio": ratio,
            }
        )

    rows.sort(key=lambda item: (item["total_ratio"], item["total_reason"], item["name"]))
    for index, row in enumerate(rows, start=1):
        row["rank"] = index

    total = {
        "plan": sum(item["plan"] for item in month_totals_map.values()),
        "reason": sum(item["reason"] for item in month_totals_map.values()),
    }
    total["ratio"] = total["reason"] / total["plan"] if total["plan"] else 0
    return month_range, rows, total, month_totals_map

def style_sheet(ws, month_range: list[int], rows: list[dict], total: dict, year: int, month_totals_map: dict[int, dict[str, int]]) -> None:
    last_month = month_range[-1] if month_range else 1
    total_columns = 4 + len(month_range) * 2 + 4

    thin = Side(style="thin", color="000000")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    center = Alignment(horizontal="center", vertical="center", wrap_text=True)
    title_fill = PatternFill("solid", fgColor="DCE6F1")
    header_fill = PatternFill("solid", fgColor="EAF2F8")
    total_fill = PatternFill("solid", fgColor="FFF2CC")

    ws.merge_cells(start_row=3, start_column=4, end_row=3, end_column=total_columns)
    ws.cell(3, 4).value = export_workbook_title(year, last_month)
    ws.cell(3, 4).font = Font(size=16, bold=True)
    ws.cell(3, 4).alignment = center
    ws.cell(3, 4).fill = title_fill
    ws.cell(3, 4).border = border

    ws.cell(5, 4).value = "统计对象"
    ws.cell(6, 4).value = ""
    current_col = 5
    for month in month_range:
        ws.merge_cells(start_row=5, start_column=current_col, end_row=5, end_column=current_col + 1)
        ws.cell(5, current_col).value = f"{month}月"
        ws.cell(6, current_col).value = "班数"
        ws.cell(6, current_col + 1).value = "目标事件班数"
        current_col += 2
    ws.merge_cells(start_row=5, start_column=current_col, end_row=5, end_column=current_col + 3)
    ws.cell(5, current_col).value = "累计"
    ws.cell(6, current_col).value = "总班数"
    ws.cell(6, current_col + 1).value = "目标事件总班数"
    ws.cell(6, current_col + 2).value = "目标事件占比（%）"
    ws.cell(6, current_col + 3).value = "排名"

    for col in range(4, total_columns + 1):
        ws.cell(5, col).alignment = center
        ws.cell(6, col).alignment = center
        ws.cell(5, col).border = border
        ws.cell(6, col).border = border
        ws.cell(5, col).fill = header_fill
        ws.cell(6, col).fill = header_fill
        ws.cell(5, col).font = Font(bold=True)
        ws.cell(6, col).font = Font(bold=True)

    start_row = 7
    for row_idx, row in enumerate(rows, start=start_row):
        row_fill = airline_row_fill(row["name"])
        ws.cell(row_idx, 4).value = row["name"]
        ws.cell(row_idx, 4).alignment = center
        ws.cell(row_idx, 4).border = border
        if row_fill:
            ws.cell(row_idx, 4).fill = row_fill
        col = 5
        for month in month_range:
            month_data = row["months"][month]
            ws.cell(row_idx, col).value = month_data["plan"] if month_data["plan"] is not None else None
            ws.cell(row_idx, col + 1).value = month_data["reason"] if month_data["reason"] is not None else None
            ws.cell(row_idx, col).alignment = center
            ws.cell(row_idx, col + 1).alignment = center
            ws.cell(row_idx, col).border = border
            ws.cell(row_idx, col + 1).border = border
            if row_fill:
                ws.cell(row_idx, col).fill = row_fill
                ws.cell(row_idx, col + 1).fill = row_fill
            col += 2
        ws.cell(row_idx, col).value = row["total_plan"]
        ws.cell(row_idx, col + 1).value = row["total_reason"]
        ws.cell(row_idx, col + 2).value = row["total_ratio"]
        ws.cell(row_idx, col + 3).value = row["rank"]
        for current in range(col, col + 4):
            ws.cell(row_idx, current).alignment = center
            ws.cell(row_idx, current).border = border
            if row_fill:
                ws.cell(row_idx, current).fill = row_fill
        ws.cell(row_idx, col + 2).number_format = "0.00%"

    total_row_idx = start_row + len(rows)
    ws.cell(total_row_idx, 4).value = "合计"
    ws.cell(total_row_idx, 4).alignment = center
    ws.cell(total_row_idx, 4).fill = total_fill
    ws.cell(total_row_idx, 4).border = border

    col = 5
    for month in month_range:
        month_totals = month_totals_map.get(month, {})
        month_plan = int(month_totals.get("plan", sum(row["months"][month]["plan"] for row in rows)))
        month_reason = int(month_totals.get("reason", sum(row["months"][month]["reason"] for row in rows)))
        ws.cell(total_row_idx, col).value = month_plan
        ws.cell(total_row_idx, col + 1).value = month_reason
        ws.cell(total_row_idx, col).alignment = center
        ws.cell(total_row_idx, col + 1).alignment = center
        ws.cell(total_row_idx, col).fill = total_fill
        ws.cell(total_row_idx, col + 1).fill = total_fill
        ws.cell(total_row_idx, col).border = border
        ws.cell(total_row_idx, col + 1).border = border
        col += 2

    ws.cell(total_row_idx, col).value = total["plan"]
    ws.cell(total_row_idx, col + 1).value = total["reason"]
    ws.cell(total_row_idx, col + 2).value = total["ratio"]
    ws.cell(total_row_idx, col + 3).value = ""
    for current in range(col, col + 4):
        ws.cell(total_row_idx, current).alignment = center
        ws.cell(total_row_idx, current).fill = total_fill
        ws.cell(total_row_idx, current).border = border
    ws.cell(total_row_idx, col + 2).number_format = "0.00%"

    for row_idx in range(3, total_row_idx + 1):
        for col_idx in range(4, total_columns + 1):
            ws.cell(row_idx, col_idx).alignment = center

    for col_idx in range(4, total_columns + 1):
        max_width = 0
        for row_idx in range(3, total_row_idx + 1):
            cell = ws.cell(row_idx, col_idx)
            if cell.coordinate in ws.merged_cells:
                if cell.row != 3 and cell.row != 5:
                    continue
            current_width = display_width(cell.value)
            if current_width > max_width:
                max_width = current_width
        if col_idx == 4:
            width = min(max(max_width + 2, 14), 20)
        elif col_idx == total_columns:
            width = min(max(max_width + 2, 8), 10)
        else:
            width = min(max(max_width + 2, 10), 16)
        ws.column_dimensions[get_column_letter(col_idx)].width = width

    ws.row_dimensions[3].height = 28
    ws.row_dimensions[5].height = 24
    ws.row_dimensions[6].height = 34
    for row_idx in range(start_row, total_row_idx + 1):
        ws.row_dimensions[row_idx].height = 24
