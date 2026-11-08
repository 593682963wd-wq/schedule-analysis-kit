"""作者：Wangyuan；日期：2026-10-29。离线通用核心，输入由调用方显式提供。"""
from __future__ import annotations
from typing import Any
import re
HEADER_COLS = ['调整类型', '日期', '航班号', '机号', '出发机场', '到达机场', '局飞', '局达', '预飞', '预达', '调整原因（对内）', '调整原因（对外）']

def _clean(s: Any) -> str:
    if s is None:
        return ''
    return re.sub('\\s+', '', str(s)).strip()

def split_reg(raw: str) -> tuple[str, str]:
    """拆分显式“新标识(原旧标识)”，不修正标识、不猜前缀。"""
    raw = _clean(raw)
    m = re.match('^(.*?)[（(]原(.*?)[)）]\\s*$', raw)
    if m:
        return (normalize_reg(m.group(1).strip()), normalize_reg(m.group(2).strip()))
    return (normalize_reg(raw), '')

def normalize_reg(reg: str) -> str:
    return _clean(reg).upper()

def split_time(raw: str) -> tuple[str, str]:
    """时间拆分：'08:35(原07:15)' -> ('08:35','07:15')；'20:30' -> ('20:30','')；'/' -> ('','')。"""
    raw = _clean(raw)
    if raw in {'', '/', '-', '—'}:
        return ('', '')
    m = re.match('^(.*?)[（(]原(.*?)[)）]\\s*$', raw)
    if m:
        new = m.group(1).strip()
        old = m.group(2).strip()
        return ('' if new in {'/', '-'} else new, '' if old in {'/', '-'} else old)
    return (raw, '')

def _map_header(header: list[str]) -> list[str]:
    """把抽出的表头列名归一到 HEADER_COLS（容忍 OCR/换行噪声）。

    pdfplumber 抽的表头本就是精确列名，故优先精确匹配；
    再退化到双向包含。**不要**用「前两字 startswith」这类模糊匹配——
    『调整类型/调整原因（对内）/调整原因（对外）』都以「调整」开头会互相串列。
    """
    mapped = []
    for h in header:
        h2 = _clean(h)
        if h2 in HEADER_COLS:
            mapped.append(h2)
            continue
        cands = [c for c in HEADER_COLS if h2 and (h2 in c or c in h2)]
        if cands:
            mapped.append(max(cands, key=lambda c: len(set(c) & set(h2))))
        else:
            mapped.append(h2)
    return mapped

def _row_from_table(raw: list, idx: dict[str, int]) -> dict[str, str]:

    def g(col: str) -> str:
        i = idx.get(col)
        if i is None or i >= len(raw):
            return ''
        return _clean(raw[i])
    reg_new, reg_old = split_reg(g('机号'))
    dep_new, dep_old = split_time(g('局飞'))
    arr_new, arr_old = split_time(g('局达'))
    est_dep, _ = split_time(g('预飞'))
    est_arr, _ = split_time(g('预达'))
    return {'type': g('调整类型'), 'date': g('日期'), 'flight': g('航班号'), 'reg': reg_new, 'reg_old': reg_old, 'dep': g('出发机场'), 'arr': g('到达机场'), 'sched_dep': dep_new, 'sched_dep_old': dep_old, 'sched_arr': arr_new, 'sched_arr_old': arr_old, 'est_dep': est_dep, 'est_arr': est_arr, 'reason_in': g('调整原因（对内）'), 'reason_out': g('调整原因（对外）')}

def _tabular_text_rows(lines: list[str]) -> tuple[list[dict[str, str]], bool]:
    """解析从 文本表格 复制出来的 TSV 或竖线分隔表格。"""
    header_index = -1
    header_cells: list[str] = []
    delimiter = ''
    for index, line in enumerate(lines):
        if '航班号' not in line or '调整' not in line:
            continue
        if '\t' in line:
            delimiter = '\t'
        elif '|' in line:
            delimiter = '|'
        else:
            continue
        header_index = index
        header_cells = [cell.strip() for cell in line.split(delimiter)]
        break
    if header_index < 0:
        return ([], False)
    mapped = _map_header([_clean(cell) for cell in header_cells])
    indexes = {name: index for index, name in enumerate(mapped)}
    rows: list[dict[str, str]] = []
    for line in lines[header_index + 1:]:
        if not line.strip():
            continue
        cells = [cell.strip() for cell in line.split(delimiter)]
        row = _row_from_table(cells, indexes)
        if _clean(row.get('flight')) or _clean(row.get('type')):
            rows.append(row)
    return (rows, True)
