"""Read-only detail for 2026-10-08-analysis.md; two bounded queries at a time."""

import concurrent.futures
import json
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

START = datetime.fromisoformat("2026-10-02T21:00:00+00:00")
END = datetime.fromisoformat("2026-10-08T07:05:00+00:00")
TASKS = []


def add(name, query, begin=START, finish=END, step=None):
    params = {"query": query, "timeout": "20s"}
    if step is None:
        endpoint = "query"
        params["time"] = finish.timestamp()
    else:
        endpoint = "query_range"
        params.update(start=begin.timestamp(), end=finish.timestamp(), step=step)
    TASKS.append((name, endpoint, params))


add("client_media_failures", 'sum by(audience)(increase(vmsh_client_media_load_failures_total[468300s]))')
add("http_over10", 'sum by(route)(increase(vmsh_http_request_duration_seconds_count[468300s])) - sum by(route)(increase(vmsh_http_request_duration_seconds_bucket{le="10.0"}[468300s]))')
add("process_restarts", 'sum by(job)(changes(process_start_time_seconds[468300s]))')
add("probe_success_min", 'min_over_time(probe_success[468300s])')
add("media_outcomes_hourly", "sum by(stage,outcome)(increase(vmsh_media_stage_duration_seconds_count[1h]))", step=3600)
add("media_avg_hourly", "sum by(stage)(increase(vmsh_media_stage_duration_seconds_sum[1h])) / sum by(stage)(increase(vmsh_media_stage_duration_seconds_count[1h]))", step=3600)
add("http_5xx_hourly", 'sum by(route,status)(increase(vmsh_http_requests_total{status=~"5.."}[1h]))', step=3600)
add("queue_max_5m", "max by(role)(max_over_time(vmsh_db_waiting[5m]))", step=300)
add("up_failures_5m", "sum_over_time((1-up)[5m:15s])", step=300)
add("cpu_1m", '100*(1-avg(rate(node_cpu_seconds_total{mode="idle"}[1m])))', step=60)
add("problems_p95", 'histogram_quantile(.95,sum by(le)(rate(vmsh_http_request_duration_seconds_bucket{route="/student/api/v1/courses/{course_id}/lessons/{group_lesson_id}/problems"}[5m])))', step=300)
add("content_p95", 'histogram_quantile(.95,sum by(le)(rate(vmsh_http_request_duration_seconds_bucket{route="/student/api/v1/group-lessons/{group_lesson_id}/content/{kind}"}[5m])))', step=300)
add("read_wait_p95", 'histogram_quantile(.95,sum by(le)(rate(vmsh_db_admission_wait_seconds_bucket{role="read"}[5m])))', step=300)
for index in range(6):
    begin = START + timedelta(days=index)
    finish = min(begin + timedelta(days=1), END)
    window = f"{int((finish - begin).total_seconds())}s"
    prefix = f"day_{3 + index:02d}"
    add(prefix + "_media_outcomes", f"sum by(stage,outcome)(increase(vmsh_media_stage_duration_seconds_count[{window}]))", begin, finish)
    add(prefix + "_media_average", f"sum by(stage)(increase(vmsh_media_stage_duration_seconds_sum[{window}])) / sum by(stage)(increase(vmsh_media_stage_duration_seconds_count[{window}]))", begin, finish)
    add(prefix + "_media_p95", f"histogram_quantile(.95,sum by(le,stage)(increase(vmsh_media_stage_duration_seconds_bucket[{window}])))", begin, finish)


def run(task):
    name, endpoint, params = task
    url = "http://127.0.0.1:9090/api/v1/" + endpoint + "?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            result = json.load(response)
    except Exception as error:
        result = {"error": str(error)}
    return name, {"endpoint": endpoint, "parameters": params, "result": result}


with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
    output = dict(pool.map(run, TASKS))
print(json.dumps(output, separators=(",", ":")))
