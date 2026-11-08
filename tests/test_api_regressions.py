"""作者：Wangyuan；日期：2026-11-08。合成统计口径、类型及导出回归。"""
from io import BytesIO
from pathlib import Path
import os
import shutil
import subprocess
import unittest
import pandas as pd
from openpyxl import load_workbook
from schedule import coflight, dynamic_aggregates, ranking, export
from schedule.taxi_events import AirportStats


class ApiRegressionTests(unittest.TestCase):
    def test_numeric_flight_times_keep_their_types(self):
        for std in (1700000000, 1700000000000):
            rows = coflight.normalize_flights([{'flight_no': 'ZZ100', 'origin': 'XXXX', 'destination': 'YYYY', 'std': std}], '2023-11-14', source='synthetic')
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]['std'], '2023-11-14T22:13')

    def test_dynamic_percentiles_use_nearest_rank(self):
        self.assertEqual(dynamic_aggregates.percentile(pd.Series([1, 2, 3]), 0.8), 3)
        frame = pd.DataFrame({'airport_code': ['XXX'] * 3, 'airport_name': ['合成机场'] * 3, 'direction': ['出港'] * 3, 'stand_group': ['桥位'] * 3, 'stand_normalized': ['1'] * 3, 'taxi_metric': [1, 2, 3]})
        self.assertEqual(dynamic_aggregates.summarize_taxi(frame).iloc[0]['P80(分)'], 3)

    def test_dynamic_source_parses_as_python311(self):
        interpreter = os.environ.get('PYTHON311_BIN') or shutil.which('python3.11')
        if not interpreter:
            self.skipTest('本环境未提供Python 3.11解释器，不能代替真实语法验证')
        process = subprocess.run([interpreter, '-B', '-c', 'import ast,sys;ast.parse(sys.stdin.read())'], input=Path(dynamic_aggregates.__file__).read_text(), capture_output=True, text=True)
        self.assertEqual(process.returncode, 0, process.stderr)

    def test_ranking_export_treats_if_name_as_literal(self):
        name = '=IF(1,2,3)'
        store = {'entities': [name], 'years': {'2040': {'months': {'1': {'review_status': 'confirmed', 'rows': [{'name': name, 'plan': 10, 'reason': 1}]}}}}}
        workbook = load_workbook(BytesIO(export.ranking_bytes(store, 2040)), data_only=False)
        cells = [cell for row in workbook.active for cell in row if cell.value == name]
        self.assertTrue(cells); self.assertTrue(all(cell.data_type == 's' for cell in cells)); workbook.close()

    def test_invalid_reason_counts_are_flagged(self):
        for reason in (-1, 11):
            _, issues = ranking.validate_rows([{'name': 'A', 'plan': 10, 'reason': reason}], {}, 2040, 1, {'entities': ['A']})
            self.assertTrue(any('班数' in item['message'] for item in issues))

    def test_zero_events_positive_percentage_cannot_infer_plan(self):
        self.assertIsNone(ranking.infer_plan(0, '2%'))

    def test_total_taxi_is_unknown_if_one_direction_missing(self):
        row = AirportStats('XXX', '合成机场', '合成机场', [10], [], [], [], [])
        self.assertIsNone(row.taxi_total_avg)


if __name__ == '__main__':
    unittest.main()
