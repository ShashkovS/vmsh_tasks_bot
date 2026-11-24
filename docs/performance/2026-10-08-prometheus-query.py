"""Read-only localhost Prometheus audit; 2026-10-08-analysis.md.

Run via SSH stdin; emits only canonical metric labels and aggregate values.
At most two concurrent queries, each limited to 20 seconds server-side.
"""

import concurrent.futures
import json
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

START = datetime.fromisoformat("2026-10-02T21:00:00+00:00")
END = datetime.fromisoformat("2026-10-08T07:05:00+00:00")
BASE = "http://127.0.0.1:9090/api/v1/"


def request(endpoint, params):
    url = BASE + endpoint + "?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            return json.load(response)
    except Exception as error:
        return {"error": str(error)}


def queries(seconds, detailed=False):
    window = f"{seconds}s"
    inc = lambda metric: f"increase({metric}[{window}])"
    duration = "vmsh_http_request_duration_seconds"
    result = {
        "http_count": f"sum by(route,method)({inc(duration + '_count')})",
        "http_p95": f"histogram_quantile(.95,sum by(le,route)({inc(duration + '_bucket')}))",
        "http_status": f"sum by(route,status)({inc('vmsh_http_requests_total')})",
        "http_over1": f"sum({inc(duration + '_count')}) - sum({inc(duration + '_bucket{le=\"1.0\"}')})",
        "cpu_avg": f"avg_over_time((100*(1-avg(rate(node_cpu_seconds_total{{mode=\"idle\"}}[1m]))))[{window}:1m])",
        "cpu_max": f"max_over_time((100*(1-avg(rate(node_cpu_seconds_total{{mode=\"idle\"}}[1m]))))[{window}:1m])",
        "memory_available_min": f"min_over_time(node_memory_MemAvailable_bytes[{window}])",
        "db_queue_max": f"max_over_time(vmsh_db_waiting[{window}])",
        "db_wait_p95": f"histogram_quantile(.95,sum by(le,role)({inc('vmsh_db_admission_wait_seconds_bucket')}))",
        "db_hold_p95": f"histogram_quantile(.95,sum by(le,role)({inc('vmsh_db_slot_hold_seconds_bucket')}))",
        "loop_p99": f"histogram_quantile(.99,sum by(le)({inc('vmsh_event_loop_lag_seconds_bucket')}))",
        "up_min": f"min_over_time(up[{window}])",
    }
    if not detailed:
        return result
    result.update({
        "http_avg": f"sum by(route)({inc(duration + '_sum')}) / sum by(route)({inc(duration + '_count')})",
        "http_p99": f"histogram_quantile(.99,sum by(le,route)({inc(duration + '_bucket')}))",
        "http_over1_by_route": f"sum by(route)({inc(duration + '_count')}) - sum by(route)({inc(duration + '_bucket{le=\"1.0\"}')})",
        "http_over5_by_route": f"sum by(route)({inc(duration + '_count')}) - sum by(route)({inc(duration + '_bucket{le=\"5.0\"}')})",
        "backend_rps_max": f"max_over_time((sum(rate(vmsh_http_requests_total[1m])))[{window}:1m])",
        "nginx_rps_max": f"max_over_time(rate(nginx_http_requests_total[1m])[{window}:1m])",
        "iowait_max": f"max_over_time((100*avg(rate(node_cpu_seconds_total{{mode=\"iowait\"}}[1m])))[{window}:1m])",
        "disk_busy_max": f"max_over_time(rate(node_disk_io_time_seconds_total[1m])[{window}:1m])",
        "filesystem_available_min": f"min_over_time(node_filesystem_avail_bytes{{fstype!~\"tmpfs|overlay|squashfs\"}}[{window}])",
        "cpu_pressure_max": f"max_over_time(rate(node_pressure_cpu_waiting_seconds_total[1m])[{window}:1m])",
        "io_pressure_max": f"max_over_time(rate(node_pressure_io_waiting_seconds_total[1m])[{window}:1m])",
        "up_failed_samples": f"sum_over_time((1-up)[{window}:15s])",
        "up_sample_count": f"count_over_time(up[{window}])",
        "websocket_max": f"max_over_time(vmsh_websocket_connections[{window}])",
        "loop_over200ms": f"sum({inc('vmsh_event_loop_lag_seconds_count')}) - sum({inc('vmsh_event_loop_lag_seconds_bucket{le=\"0.2\"}')})",
        "loop_over1": f"sum({inc('vmsh_event_loop_lag_seconds_count')}) - sum({inc('vmsh_event_loop_lag_seconds_bucket{le=\"1.0\"}')})",
        "media_count": f"sum by(stage,outcome)({inc('vmsh_media_stage_duration_seconds_count')})",
        "media_avg": f"sum by(stage)({inc('vmsh_media_stage_duration_seconds_sum')}) / sum by(stage)({inc('vmsh_media_stage_duration_seconds_count')})",
        "media_p95": f"histogram_quantile(.95,sum by(le,stage)({inc('vmsh_media_stage_duration_seconds_bucket')}))",
        "client_media_failures": f"sum by(audience)({inc('vmsh_client_media_load_failures_total')})",
    })
    for name, metric in (("db_wait", "vmsh_db_admission_wait_seconds"), ("db_hold", "vmsh_db_slot_hold_seconds")):
        result[name + "_avg"] = f"sum by(role)({inc(metric + '_sum')}) / sum by(role)({inc(metric + '_count')})"
        result[name + "_p99"] = f"histogram_quantile(.99,sum by(le,role)({inc(metric + '_bucket')}))"
        result[name + "_count"] = f"sum by(role)({inc(metric + '_count')})"
    return result


windows = {"full": (START, END, True)}
for index in range(6):
    begin = START + timedelta(days=index)
    finish = min(begin + timedelta(days=1), END)
    windows[f"day_2026-10-{3 + index:02d}"] = (begin, finish, False)
windows["before_correction"] = (START, datetime.fromisoformat("2026-10-04T12:31:00+00:00"), True)
windows["after_correction"] = (datetime.fromisoformat("2026-10-04T12:35:00+00:00"), END, True)

output = {"start": START.isoformat(), "end": END.isoformat(), "day_timezone": "Asia/Nicosia", "windows": {}, "ranges": {}}
tasks = []
for name, (begin, finish, detailed) in windows.items():
    output["windows"][name] = {"start": begin.isoformat(), "end": finish.isoformat(), "queries": {}, "results": {}}
    for key, query in queries(int((finish - begin).total_seconds()), detailed).items():
        output["windows"][name]["queries"][key] = query
        tasks.append((name, key, "query", {"query": query, "time": finish.timestamp(), "timeout": "20s"}))

range_queries = {
    "cpu": '100*(1-avg(rate(node_cpu_seconds_total{mode="idle"}[1m])))',
    "backend_rps": "sum(rate(vmsh_http_requests_total[1m]))",
    "db_queue": "sum by(role)(vmsh_db_waiting)",
    "memory_available": "node_memory_MemAvailable_bytes",
    "up": "up",
    "http_5xx": 'sum by(route)(increase(vmsh_http_requests_total{status=~"5.."}[5m]))',
    "problem_list_p95": 'histogram_quantile(.95,sum by(le)(rate(vmsh_http_request_duration_seconds_bucket{route="/student/api/v1/courses/{course_id}/lessons/{group_lesson_id}/problems"}[5m])))',
    "content_p95": 'histogram_quantile(.95,sum by(le)(rate(vmsh_http_request_duration_seconds_bucket{route="/student/api/v1/group-lessons/{group_lesson_id}/content/{kind}"}[5m])))',
    "db_read_wait_p95": 'histogram_quantile(.95,sum by(le)(rate(vmsh_db_admission_wait_seconds_bucket{role="read"}[5m])))',
    "db_read_hold_p95": 'histogram_quantile(.95,sum by(le)(rate(vmsh_db_slot_hold_seconds_bucket{role="read"}[5m])))',
}
for key, query in range_queries.items():
    output["ranges"][key] = {"query": query}
    tasks.append(("range", key, "query_range", {"query": query, "start": START.timestamp(), "end": END.timestamp(), "step": 300, "timeout": "20s"}))


def run(task):
    name, key, endpoint, params = task
    return name, key, request(endpoint, params)


with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
    for name, key, result in pool.map(run, tasks):
        if name == "range":
            output["ranges"][key]["result"] = result
        else:
            output["windows"][name]["results"][key] = result
output["targets"] = request("targets", {})
output["rules"] = request("rules", {})
print(json.dumps(output, separators=(",", ":")))
