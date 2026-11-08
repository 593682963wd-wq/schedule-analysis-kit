"""作者：Wangyuan；日期：2026-10-29。离线通用核心，输入由调用方显式提供。"""
from __future__ import annotations
from typing import Any
import pandas as pd
import math
TYPE_ONLY_STANDS = set()

def percentile(values: pd.Series, q: float) -> float | None:
    if not 0 <= q <= 1:
        raise ValueError('分位值须在0至1之间')
    clean = sorted(float(value) for value in values.dropna() if math.isfinite(float(value)))
    if not clean:
        return None
    return round(clean[max(0, math.ceil(q * len(clean)) - 1)], 1)

def avg(values: pd.Series) -> float | None:
    clean = values.dropna()
    if clean.empty:
        return None
    return round(float(clean.mean()), 1)

def pct(part: int | float, total: int | float) -> float:
    return round(float(part) / float(total) * 100, 1) if total else 0.0

def top_values(series: pd.Series, total: int | None=None, limit: int=5, exclude_values: set[str] | None=None) -> str:
    clean = series.dropna()
    clean = clean[clean.astype(str).str.strip() != '']
    if exclude_values:
        clean = clean[~clean.astype(str).isin(exclude_values)]
    if clean.empty:
        return ''
    denominator = total or len(clean)
    return '；'.join((f'{idx} {count}架/{pct(count, denominator)}%' for idx, count in clean.value_counts().head(limit).items()))

def summarize_distribution(events: pd.DataFrame) -> pd.DataFrame:
    grouped = events.groupby(['airport_code', 'airport_name', 'airport_role', 'direction', 'stand_group'], dropna=False)
    rows: list[dict[str, Any]] = []
    totals = events.groupby(['airport_code', 'direction']).size().to_dict()
    for keys, group in grouped:
        airport_code, airport_name, airport_role, direction, stand_group = keys
        total = totals.get((airport_code, direction), len(group))
        rows.append({'机场三字码': airport_code, '机场': airport_name, '角色': airport_role, '方向': direction, '机位类型': stand_group, '样本数': len(group), '占比': pct(len(group), total), 'Top机位': top_values(group['stand_normalized'], total=len(group), limit=8, exclude_values=TYPE_ONLY_STANDS), '有效滑行样本': int(group['taxi_metric'].notna().sum()), '平均滑行(分)': avg(group['taxi_metric']), 'P50(分)': percentile(group['taxi_metric'], 0.5), 'P80(分)': percentile(group['taxi_metric'], 0.8), 'P90(分)': percentile(group['taxi_metric'], 0.9)})
    frame = pd.DataFrame(rows)
    return frame if frame.empty else frame.sort_values(['机场三字码', '方向', '样本数'], ascending=[True, True, False])

def summarize_time_patterns(events: pd.DataFrame) -> pd.DataFrame:
    columns = ['机场三字码', '机场', '方向', '时段', '样本数', '主导机位类型', '主导类型占比', '桥位占比', '远机位占比', 'Top候选机位', '有效滑行样本', '平均滑行(分)', 'P80(分)']
    rows: list[dict[str, Any]] = []
    grouped = events[events['time_bucket'] != '缺失'].groupby(['airport_code', 'airport_name', 'direction', 'time_bucket'], dropna=False)
    for keys, group in grouped:
        airport_code, airport_name, direction, bucket = keys
        group_counts = group['stand_group'].value_counts()
        top_group = group_counts.index[0] if not group_counts.empty else ''
        top_group_count = int(group_counts.iloc[0]) if not group_counts.empty else 0
        rows.append({'机场三字码': airport_code, '机场': airport_name, '方向': direction, '时段': bucket, '样本数': len(group), '主导机位类型': top_group, '主导类型占比': pct(top_group_count, len(group)), '桥位占比': pct(int((group['stand_group'] == '桥位').sum()), len(group)), '远机位占比': pct(int((group['stand_group'] == '远机位').sum()), len(group)), 'Top候选机位': top_values(group['stand_normalized'], total=len(group), limit=6, exclude_values=TYPE_ONLY_STANDS), '有效滑行样本': int(group['taxi_metric'].notna().sum()), '平均滑行(分)': avg(group['taxi_metric']), 'P80(分)': percentile(group['taxi_metric'], 0.8)})
    if not rows:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame(rows, columns=columns).sort_values(['机场三字码', '方向', '时段'])

def summarize_taxi(events: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for keys, group in events.groupby(['airport_code', 'airport_name', 'direction', 'stand_group'], dropna=False):
        airport_code, airport_name, direction, stand_group = keys
        values = group['taxi_metric'].dropna()
        if values.empty:
            continue
        rows.append({'机场三字码': airport_code, '机场': airport_name, '方向': direction, '机位类型': stand_group, '有效样本': len(values), '平均(分)': round(float(values.mean()), 1), 'P50(分)': percentile(values, 0.5), 'P80(分)': percentile(values, 0.8), 'P90(分)': percentile(values, 0.9), '最小(分)': int(values.min()), '最大(分)': int(values.max())})
    for keys, group in events.groupby(['airport_code', 'airport_name', 'direction', 'stand_normalized'], dropna=False):
        airport_code, airport_name, direction, stand = keys
        values = group['taxi_metric'].dropna()
        if len(values) < 20:
            continue
        rows.append({'机场三字码': airport_code, '机场': airport_name, '方向': direction, '机位类型': f'具体机位:{stand}', '有效样本': len(values), '平均(分)': round(float(values.mean()), 1), 'P50(分)': percentile(values, 0.5), 'P80(分)': percentile(values, 0.8), 'P90(分)': percentile(values, 0.9), '最小(分)': int(values.min()), '最大(分)': int(values.max())})
    frame = pd.DataFrame(rows)
    return frame if frame.empty else frame.sort_values(['机场三字码', '方向', '有效样本'], ascending=[True, True, False])

def summarize_volume_heatmap(events: pd.DataFrame, *, airports: dict[str,dict[str,str]]) -> list[dict[str, Any]]:
    buckets = [f'{hour:02d}:00-{(hour + 3) % 24:02d}:00' for hour in range(0, 24, 3)]
    rows: list[dict[str, Any]] = []
    grouped = events[events['time_bucket'] != '缺失'].groupby(['airport_code', 'airport_name', 'direction', 'time_bucket'], dropna=False)
    counts = grouped.size().to_dict()
    max_count = max(counts.values()) if counts else 1
    for code, meta in airports.items():
        for direction in ('出港', '进港'):
            for bucket in buckets:
                count = int(counts.get((code, meta['name'], direction, bucket), 0))
                rows.append({'airport_code': code, 'airport_name': meta['name'], 'direction': direction, 'bucket': bucket, 'count': count, 'intensity': round(count / max_count, 3) if max_count else 0})
    return rows

def heatmap_matrix(rows: list[dict[str, Any]], *, airports: dict[str,dict[str,str]]) -> list[dict[str, Any]]:
    buckets = [f'{hour:02d}:00-{(hour + 3) % 24:02d}:00' for hour in range(0, 24, 3)]
    matrix: list[dict[str, Any]] = []
    for code, meta in airports.items():
        for direction in ('出港', '进港'):
            cells = [next((item for item in rows if item['airport_code'] == code and item['direction'] == direction and (item['bucket'] == bucket)), {'bucket': bucket, 'count': 0, 'intensity': 0}) for bucket in buckets]
            matrix.append({'label': f"{meta['name']}{direction}", 'airport_code': code, 'direction': direction, 'cells': cells})
    return matrix

def summarize_route_network(events: pd.DataFrame, limit: int=16) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for keys, group in events.groupby(['airport_code', 'airport_name', 'direction', 'other_airport_code', 'other_city'], dropna=False):
        airport_code, airport_name, direction, other_code, other_city = keys
        if not other_code and (not other_city):
            continue
        delay_values = group['delay_metric'].dropna() if 'delay_metric' in group else pd.Series(dtype=float)
        rows.append({'机场三字码': airport_code, '机场': airport_name, '方向': direction, '对端机场': other_code, '对端城市': other_city, '航线标签': f'{airport_name}{direction}-{other_city or other_code}', '样本数': len(group), '桥位占比': pct(int((group['stand_group'] == '桥位').sum()), len(group)), '远机位占比': pct(int((group['stand_group'] == '远机位').sum()), len(group)), '平均滑行(分)': avg(group['taxi_metric']), 'P80滑行(分)': percentile(group['taxi_metric'], 0.8), '平均延误(分)': avg(delay_values), '候选机位': top_values(group['stand_normalized'], total=len(group), limit=4, exclude_values=TYPE_ONLY_STANDS)})
    if not rows:
        return pd.DataFrame()
    frame = pd.DataFrame(rows)
    return frame if frame.empty else frame.sort_values('样本数', ascending=False).head(limit)
