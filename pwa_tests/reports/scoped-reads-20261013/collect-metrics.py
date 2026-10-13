"""Read-only Prometheus comparison; bounded route/category labels, no identities."""
import argparse
import concurrent.futures
import json
import urllib.parse
import urllib.request
from datetime import datetime

parser = argparse.ArgumentParser()
parser.add_argument('--start', required=True)
parser.add_argument('--end', required=True)
args = parser.parse_args()
start, end = map(datetime.fromisoformat, (args.start, args.end))
window = f'{int((end-start).total_seconds())}s'
assert 60 <= (end-start).total_seconds() <= 86400
jobs = {}
def increase(metric):
    return f'increase({metric}[{window}])'
http = 'vmsh_http_request_duration_seconds'
jobs['httpCount'] = f'sum by(route,method)({increase(http+"_count")})'
jobs['httpMean'] = f'sum by(route,method)({increase(http+"_sum")})/sum by(route,method)({increase(http+"_count")})'
jobs['httpStatus'] = f'sum by(route,method,status)({increase("vmsh_http_requests_total")})'
for p in (.95,.99):
    jobs[f'httpP{int(p*100)}'] = f'histogram_quantile({p},sum by(le,route,method)({increase(http+"_bucket")}))'
for kind,metric in [('admission','vmsh_db_admission_wait_seconds'),('hold','vmsh_db_slot_hold_seconds'),('projection','vmsh_projection_duration_seconds')]:
    label = 'projection' if kind=='projection' else 'role'
    jobs[kind+'Count'] = f'sum by({label})({increase(metric+"_count")})'
    for p in (.95,.99):
        jobs[kind+f'P{int(p*100)}'] = f'histogram_quantile({p},sum by(le,{label})({increase(metric+"_bucket")}))'
jobs['queueMax'] = f'max by(role)(max_over_time(vmsh_db_waiting[{window}]))'
jobs['cacheReads'] = f'sum by(cache,outcome)({increase("vmsh_read_cache_requests_total")})'
jobs['cacheBytesMax'] = f'max by(cache)(max_over_time(vmsh_read_cache_bytes[{window}]))'
jobs['loopP99'] = f'histogram_quantile(.99,sum by(le)({increase("vmsh_event_loop_lag_seconds_bucket")}))'

def read(item):
    key, query = item
    params = urllib.parse.urlencode({'query':query,'time':end.timestamp(),'timeout':'20s'})
    try:
        with urllib.request.urlopen('http://127.0.0.1:9090/api/v1/query?'+params,timeout=25) as response:
            result = json.load(response)
        assert result['status']=='success'
        return key,result['data']['result']
    except Exception as error:
        return key,{'errorType':type(error).__name__}

with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
    result = dict(pool.map(read,jobs.items()))
print(json.dumps({'start':args.start,'end':args.end,'windowSeconds':int((end-start).total_seconds()),'results':result,'personalDataIncluded':False}))
