"""作者：Wangyuan；日期：2026-10-29。合成时刻及统计回归。"""
import unittest,io
from datetime import date
from openpyxl import load_workbook
from schedule import clocks,compare_duration,weekly,route_window,taxi_input,taxi,ranking,export,ocr_consistency,coordination,change_table,taxi_quantiles,coflight
class ScheduleTests(unittest.TestCase):
    def test_clock(self):self.assertEqual(clocks.parse_clock_minutes("25:30"),1530);self.assertEqual(clocks.interval_minutes(1410,30)[0],60)
    def test_clock_invalid(self):
        for value in ["10:60","99:00",float("nan")]:
            with self.subTest(value=value),self.assertRaises(ValueError):clocks.parse_clock_minutes(value)
    def test_history_direction(self):
        result=compare_duration.weighted_history([{"origin":"A","destination":"B","duration":10,"weight":1},{"origin":"A","destination":"B","duration":20,"weight":3}]);self.assertEqual(result[("A","B")],18);self.assertNotIn(("B","A"),result)
    def test_history_invalid(self):
        with self.assertRaises(ValueError):compare_duration.weighted_history([{"origin":"A","destination":"B","duration":10,"weight":0}])
    def test_compare_missing(self):
        row={"id":"synthetic","origin":"A","destination":"B","departure":"23:30","arrival":"00:30"};out=compare_duration.compare_durations([row],{},gap_boundaries=(1,3));self.assertEqual(out[0]["planned_minutes"],60);self.assertIsNone(out[0]["gap_minutes"])
    def test_compare_gap(self):
        row={"id":"synthetic","origin":"A","destination":"B","departure":"23:30","arrival":"00:30"};out=compare_duration.compare_durations([row],{("A","B"):65},gap_boundaries=(1,3));self.assertEqual(out[0]["band"],2)
    def test_weekly(self):
        row=weekly.FlightRow(1,"ZZ100",None,"","A-B",[1,3],legs=[{"dep":"A","arr":"B","std_min":1410,"sta_min":30}]);self.assertEqual(row.block_minutes,60);self.assertEqual(weekly.daily_count([row])["by_day_flights"][1],1)
    def test_weekly_duplicate(self):
        row=weekly.FlightRow(1,"ZZ100",None,"","A-B",[1]);
        with self.assertRaises(ValueError):weekly.compare_versions([row,row],[row])
    def test_midnight_window(self):self.assertTrue(route_window.within_n_hours("23:50","00:10",1));self.assertFalse(route_window.within_n_hours("10:00","12:00",1))
    def test_bad_schedule(self):self.assertIsNone(route_window.time_to_minutes("25:00"));self.assertIsNone(route_window.time_to_minutes("10:60"))
    def test_runway(self):
        self.assertEqual(taxi_input.clean_runway("09L"),"09L");
        with self.assertRaises(ValueError):taxi_input.clean_runway("99")
    def test_taxi_time(self):self.assertEqual(taxi.parse_time_to_seconds("02:30"),150);self.assertIsNone(taxi.parse_time_to_seconds("bad"))
    def test_formula_export(self):
        wb=load_workbook(io.BytesIO(export.table_bytes([{"value":"=IF(1,2,3)"}],columns=("value",))));self.assertEqual(wb.active["A2"].data_type,"s");wb.close()
    def test_infer_unique(self):self.assertEqual(ranking.infer_reason(100,"2%"),2);self.assertIsNone(ranking.infer_plan(0,"0%"))
    def test_ocr_consistency(self):self.assertEqual(ocr_consistency.validated_cancel_total(100,[(2,2.0)],absolute_tolerance=.1,relative_tolerance=.01),100)
    def test_ocr_conflict(self):self.assertIsNone(ocr_consistency.validated_cancel_total(100,[(2,5.0)],absolute_tolerance=.1,relative_tolerance=.01))
    def test_coordination_midnight(self):
        with self.assertRaises(ValueError):coordination.diff_minutes("23:50","00:10")
    def test_coordination_business_dates(self):self.assertEqual(coordination.diff_minutes("23:50","00:10",std_date=date(2040,1,1),atd_date=date(2040,1,2)),-20)
    def test_change_tsv(self):self.assertEqual(change_table.split_time("10:00(原11:00)"),("10:00","11:00"))
    def test_coflight_no_company(self):self.assertEqual(coflight.normalize_airport("XXXX"),"XXXX")
    def test_filter_full(self):
        from schedule.filter_segments import filter_segments
        rows=[dict(fn="ZZ100",origin="A",dest="B",dep="2350"),dict(fn="YY200",origin="A",dest="B",dep="0010")]
        result=filter_segments(rows,carrier_prefix="ZZ",hours=1);self.assertTrue(result)
    def test_quantile_full(self):
        rows=[{"airport":"XXXX","flight_no":str(i),"taxi_out":v} for i,v in enumerate([1,2,3,float("nan")])]
        result,removed=taxi_quantiles.analyze_rows(rows,.5,1,upper_bound=10);self.assertEqual(len(removed),1);self.assertEqual(result["XXXX"]["n"],3)
    def test_coflight_full(self):
        rows=[{"flight_no":"ZZ100","origin":"XXXX","destination":"YYYY","std":"2040-01-01T10:00:00Z","sta":"2040-01-01T11:00:00Z"},{"flight_no":"YY200","origin":"XXXX","destination":"YYYY","std":"2040-01-01T10:30:00Z","sta":"2040-01-01T11:30:00Z"}]
        normalized=coflight.normalize_flights(rows,"2040-01-01",source="synthetic");result=coflight.analyze_coflights(normalized,carrier_prefix="ZZ",window_minutes=60);self.assertTrue(result)

if __name__=="__main__":unittest.main()
