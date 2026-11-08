"""作者：Wangyuan；日期：2026-10-29。通用表格及年度排名导出。"""
from __future__ import annotations
from io import BytesIO
from typing import Any, Iterable, Mapping
from openpyxl import Workbook
from .ranking import build_year_rows,style_sheet


def table_bytes(rows: Iterable[Mapping[str, Any]], *, columns: tuple[str,...], title: str="Data") -> bytes:
    """按显式列导出，用户文本始终写为字符串，不允许公式注入。"""
    wb=Workbook();ws=wb.active;ws.title=title
    for i,row in enumerate([dict(zip(columns,columns)),*rows],1):
        for j,key in enumerate(columns,1):
            value=row.get(key)
            if value is not None and not isinstance(value,(str,int,float,bool)):value=str(value)
            cell=ws.cell(i,j,value)
            if isinstance(value,str):cell.data_type="s"
    out=BytesIO();wb.save(out);wb.close();return out.getvalue()


def ranking_bytes(store: dict, year: int) -> bytes:
    """仅汇总调用方明确提供的数据，拒绝未确认月记录。"""
    months=store.get("years",{}).get(str(year),{}).get("months",{})
    for month in months.values():
        if month.get("review_status") != "confirmed":raise ValueError("月数据必须人工确认")
        names=[]
        for row in month.get("rows",[]):
            if type(row.get("plan")) is not int or type(row.get("reason")) is not int or not 0 <= row["reason"] <= row["plan"] or row["plan"] <= 0:raise ValueError("计数必须为合法整数，计划数大于零")
            names.append(row["name"])
        if len(names)!=len(set(names)):raise ValueError("月数据对象重复")
    month_range,rows,total,totals=build_year_rows(store,year)
    wb=Workbook();style_sheet(wb.active,month_range,rows,total,year,totals)
    for row in wb.active:
        for cell in row:
            if isinstance(cell.value,str) and cell.data_type=="f":cell.data_type="s"
    out=BytesIO();wb.save(out);wb.close();return out.getvalue()
