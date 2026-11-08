# 离线时刻与统计核心

版本 0.1.0。本项目源码采用 MIT 许可证，见 LICENSE；第三方依赖仍适用各自上游许可。

这是从已有实现筛选出的通用算法和必要离线适配，保留实用计算路径；并非任何原应用的完整迁移。未包含原始业务数据、既有文档模板、账号、网络适配、模型权重或历史仓库。来源追溯保存在独立的私有审查材料中。

## 运行

Python 3.13 已实测；源码使用 Python 3.11+ 语法，其他运行时尚未验证。在本目录执行：

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python demo.py
.venv/bin/python -m unittest discover -s tests -v
```

`demo.py` 是可直接运行的库使用示例，输入完全新造且明显标注为合成。`python demo.py --help` 查看说明。演示生成的文件/数据库都放临时目录并清理；需要处理自己的数据时，参照示例显式调用下面模块，不存在自动发现本机目录或登录操作。

## 能力与边界

所有统计接收调用方给定标准字段，原文件布局不自动猜测。coflight使用origin/destination/std/sta等标准键；带时区时间转换为UTC，未带时区视为调用方统一的同一时间基准，不可混用。循环24小时竞飞窗口不代表跨不同日期同一航班。协调时差为原预期减实际，正数表示记录提前；跨度大但缺日期会拒绝，结果是关联统计而非因果节约。taxi的两段时间字符串按分钟:秒解析。分位使用nearest-rank；缺失不补0。

仅离线合成测试和文件回读已验证。没有真实业务数据验收、当前法规适用性验证、生产部署或外部发送测试。读取自己的文件不等于可以公开其内容；输出和使用参数仍由调用方审核。

## 模块接口

接口参数以源码类型标注和测试用例为准。下表包含实现接口，带下划线的函数是保留的内部辅助接口。

| 模块 | 主要符号 |
| --- | --- |
| `schedule/change_table.py` | `_clean`, `split_reg`, `normalize_reg`, `split_time`, `_map_header`, `_row_from_table`, `_tabular_text_rows` |
| `schedule/clocks.py` | `DelayCrewDutyError`, `_coerce_number`, `parse_clock_minutes`, `parse_duration_minutes`, `format_clock`, `format_duration`, `_align_not_before`, `interval_minutes` |
| `schedule/coflight.py` | `normalize_airport`, `CoflightDataError`, `_canonical_key`, `_clean`, `_pick`, `normalize_flight_no`, `is_ambiguous_airport_city`, `_parse_date`, `parse_flight_datetime`, `normalize_flights`, `_is_self_flight`, `_relative_minutes`, `_window_bucket`, `_direction`, `analyze_coflights` |
| `schedule/compare_duration.py` | `weighted_history`, `compare_durations` |
| `schedule/coordination.py` | `ParsedRecord`, `normalize_time`, `minutes_of_hhmm`, `diff_minutes`, `fmt_diff_hhmm`, `normalize_coordinator_token`, `extract_coordinator_names`, `build_coordinator_report`, `prev_month_year`, `build_monthly_summary`, `_DepartureTiming`, `_business_date_text`, `_field_date`, `_field_value`, `_departure_timing`, `has_date_marker`, `extract_date_from_text`, `clean_chat_prefix`, `parse_record`, `reconcile_records` |
| `schedule/dynamic_aggregates.py` | `percentile`, `avg`, `pct`, `top_values`, `summarize_distribution`, `summarize_time_patterns`, `summarize_taxi`, `summarize_volume_heatmap`, `heatmap_matrix`, `summarize_route_network` |
| `schedule/export.py` | `table_bytes`, `ranking_bytes` |
| `schedule/filter_segments.py` | `filter_segments` |
| `schedule/ocr_consistency.py` | `OcrItem`, `compact_text`, `dedupe_ocr_items`, `ratio_from_count`, `validated_cancel_total` |
| `schedule/ranking.py` | `airline_row_fill`, `default_airlines`, `historical_warnings`, `Issue`, `now_text`, `stats_range_text`, `stats_cutoff_text`, `export_workbook_title`, `round_percent`, `parse_percent_text`, `display_width`, `year_store`, `normalize_name`, `best_name_match`, `parse_row_from_tokens`, `infer_reason`, `infer_plan`, `validate_rows`, `build_year_rows`, `style_sheet` |
| `schedule/route_ranking.py` | `short_city`, `RouteStats`, `_split_terms`, `_pair_from_term`, `_route_matches_term`, `_stats_in_scope`, `rank`, `_match_city`, `apply_selected_routes` |
| `schedule/route_window.py` | `parse_schedule`, `time_to_minutes`, `within_n_hours` |
| `schedule/taxi.py` | `RunwayNormalization`, `TaxiRecord`, `StandModeStats`, `OverallStats`, `display_value`, `normalize_stand`, `parse_time_to_seconds`, `natural_stand_key`, `build_overall_stats`, `build_mode_stats`, `safe_mean`, `build_area_rankings` |
| `schedule/taxi_events.py` | `AirportStats`, `normalize_text`, `parse_clock_minutes`, `parse_duration_minutes`, `is_valid_minutes`, `absolute_minutes`, `normalize_forward`, `normalize_backward_or_same`, `pick_taxi_in_metrics`, `pick_latest_close_abs`, `pick_earliest_open_abs`, `evaluate_turn_metric` |
| `schedule/taxi_input.py` | `clean_runway`, `normalize_records` |
| `schedule/taxi_quantiles.py` | `_classify_taxi`, `airport_name`, `analyze_rows` |
| `schedule/time_math.py` | `SegmentStat`, `normalize_route`, `calc_duration`, `nearest_5` |
| `schedule/weekly.py` | `load_flights`, `_fmt`, `FlightRow`, `daily_count`, `utilization`, `compare_versions` |

## 2026-11-08 协作修订

- 共飞时间保留数值时间戳类型。
- 分位采用nearest-rank，实际Python3.11兼容性已验证。
- 拒绝无效原因计数和零样本计划推断。
- 任一滑行分项缺失时总量保持未知。
- Excel字符串公式统一转义，包含=IF开头文本。

集合根目录 `verify_release.py --project domain-schedule-analytics` 可复跑合成测试和首次使用示例；本轮以集合验证报告为准。
