"""作者：Wangyuan；日期：2026-10-29。完全合成的离线库调用演示。"""
import argparse,json
argparse.ArgumentParser(description="纯合成数据演示，不联网，不读取原业务目录").parse_args()
from schedule.compare_duration import weighted_history,compare_durations
from schedule.taxi_quantiles import analyze_rows
history=weighted_history([{"origin":"合成甲","destination":"合成乙","duration":65,"weight":1}])
comparison=compare_durations([{"id":"synthetic","origin":"合成甲","destination":"合成乙","departure":"23:30","arrival":"00:30"}],history,gap_boundaries=(1,3))
quantiles,_=analyze_rows([{"airport":"合成甲机场","taxi_out":value} for value in [1,2,3]],.5,1,upper_bound=10)
print(json.dumps({"synthetic":True,"comparison":comparison,"quantiles":quantiles},ensure_ascii=False,indent=2))
