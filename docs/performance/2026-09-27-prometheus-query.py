import urllib.request,urllib.parse,json
end='2026-09-27T09:00:00Z'
queries={
'http_count':'sum by(route,method)(increase(vmsh_http_request_duration_seconds_count[48h]))',
'http_avg':'sum by(route)(increase(vmsh_http_request_duration_seconds_sum[48h])) / sum by(route)(increase(vmsh_http_request_duration_seconds_count[48h]))',
'http_p95':'histogram_quantile(0.95,sum by(le,route)(increase(vmsh_http_request_duration_seconds_bucket[48h])))',
'http_over1':'sum by(route)(increase(vmsh_http_request_duration_seconds_count[48h])) - sum by(route)(increase(vmsh_http_request_duration_seconds_bucket{le="1.0"}[48h]))',
'http_status':'sum by(route,status)(increase(vmsh_http_requests_total[48h]))',
'db_wait_avg':'sum by(role)(increase(vmsh_db_admission_wait_seconds_sum[48h]))/sum by(role)(increase(vmsh_db_admission_wait_seconds_count[48h]))',
'db_hold_avg':'sum by(role)(increase(vmsh_db_slot_hold_seconds_sum[48h]))/sum by(role)(increase(vmsh_db_slot_hold_seconds_count[48h]))',
'db_wait_p95':'histogram_quantile(.95,sum by(le,role)(increase(vmsh_db_admission_wait_seconds_bucket[48h])))',
'db_hold_p95':'histogram_quantile(.95,sum by(le,role)(increase(vmsh_db_slot_hold_seconds_bucket[48h])))',
'db_count':'sum by(role)(increase(vmsh_db_slot_hold_seconds_count[48h]))',
'db_max_queue':'max_over_time(vmsh_db_waiting[48h])',
'cpu_max':'max_over_time((100*(1-avg(rate(node_cpu_seconds_total{mode="idle"}[5m]))))[48h:5m])',
'cpu_avg':'avg_over_time((100*(1-avg(rate(node_cpu_seconds_total{mode="idle"}[5m]))))[48h:5m])',
'iowait_max':'max_over_time((100*avg(rate(node_cpu_seconds_total{mode="iowait"}[5m])))[48h:5m])',
'mem_available_min':'min_over_time(node_memory_MemAvailable_bytes[48h])',
'disk_busy_max':'max_over_time(rate(node_disk_io_time_seconds_total{device="vda"}[5m])[48h:5m])',
'up_min':'min_over_time(up[48h])',
'cpu_pressure_max':'max_over_time(rate(node_pressure_cpu_waiting_seconds_total[5m])[48h:5m])',
'io_pressure_max':'max_over_time(rate(node_pressure_io_waiting_seconds_total[5m])[48h:5m])',
'nginx_rps_max':'max_over_time(rate(nginx_http_requests_total[5m])[48h:5m])',
'backend_rps_max':'max_over_time((sum(rate(vmsh_http_requests_total[5m])))[48h:5m])',
}
out={}
for k,q in queries.items():
 try:
  url='http://127.0.0.1:9090/api/v1/query?'+urllib.parse.urlencode({'query':q,'time':end})
  out[k]=json.load(urllib.request.urlopen(url,timeout=30))
 except Exception as e: out[k]={'error':str(e)}
print(json.dumps(out))
