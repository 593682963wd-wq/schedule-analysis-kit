"""作者：Wangyuan；日期：2026-10-29。显式机场配置下的滑行表清洗。"""
from __future__ import annotations
import math
import re
import unicodedata
from typing import Any, Iterable, Mapping
from .taxi import TaxiRecord, normalize_stand, parse_time_to_seconds


def clean_runway(value: Any) -> str:
    """只规范化字符，不按机场推测跑道方向。"""
    text=unicodedata.normalize("NFKC",str(value or "")).upper().strip()
    if not re.fullmatch(r"(?:0[1-9]|[12][0-9]|3[0-6])[LRC]?", text):
        raise ValueError("跑道标识必须为 01–36，可带 L/R/C")
    return text


def normalize_records(rows: Iterable[Mapping[str, Any]], *, allowed_modes: set[str], corrections: Mapping[str,str]) -> tuple[list[TaxiRecord],list[dict[str,Any]]]:
    """从明确列名记录清洗；未知模式留在问题清单，绝不套用固定机场规则。"""
    records=[];issues=[]
    for index,row in enumerate(rows,1):
        try:
            landing=clean_runway(corrections.get(str(row.get("landing")),row.get("landing")))
            takeoff=clean_runway(corrections.get(str(row.get("takeoff")),row.get("takeoff")))
            mode=f"{landing}/{takeoff}"
            if mode not in allowed_modes:raise ValueError("模式未列入调用方允许集合")
            values=[parse_time_to_seconds(row.get(key)) for key in ("taxi_in","taxi_out","taxi_total")]
            if any(row.get(key) not in (None,"","--") and value is None for key,value in zip(("taxi_in","taxi_out","taxi_total"),values)):raise ValueError("时间格式不合法")
            if any(v is not None and (not math.isfinite(v) or v<0) for v in values):raise ValueError("滑行时长必须有限非负")
            stand=normalize_stand(row.get("stand"))
            if not stand:raise ValueError("机位不能为空")
            records.append(TaxiRecord(index,stand,str(row.get("landing")),str(row.get("takeoff")),landing,takeoff,mode,mode,*values))
        except (ValueError,TypeError) as exc:issues.append({"row":index,"reason":str(exc)})
    return records,issues
