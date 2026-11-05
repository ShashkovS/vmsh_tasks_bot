"""Read-only runtime sampling; vmshpwa/docs/cpu-incident-20261004.md."""

import json
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path


def cpu():
    return [int(value) for value in Path('/proc/stat').read_text().splitlines()[0].split()[1:9]]


def metrics():
    with urllib.request.urlopen('http://127.0.0.1:8000/metrics', timeout=10) as response:
        return dict(line.rsplit(' ', 1) for line in response.read().decode().splitlines()
                    if line.startswith(('vmsh_db_waiting{', 'vmsh_db_active{',
                                        'vmsh_http_requests_total{',
                                        'vmsh_websocket_connections{')))


before_cpu, before_metrics = cpu(), metrics()
samples = []
for _ in range(3):
    time.sleep(3)
    after_cpu, after_metrics = cpu(), metrics()
    delta = [end - start for start, end in zip(before_cpu, after_cpu)]
    requests = sum(float(value) - float(before_metrics.get(key, 0))
                   for key, value in after_metrics.items()
                   if key.startswith('vmsh_http_requests_total{'))
    samples.append(dict(
        time_utc=datetime.now(UTC).isoformat(),
        cpu_busy_percent=round(100 * (sum(delta) - delta[3] - delta[4]) / sum(delta), 2),
        io_wait_percent=round(100 * delta[4] / sum(delta), 2),
        read_waiting=sum(float(value) for key, value in after_metrics.items()
                         if key.startswith('vmsh_db_waiting{') and 'role="read"' in key),
        write_waiting=sum(float(value) for key, value in after_metrics.items()
                          if key.startswith('vmsh_db_waiting{') and 'role="write"' in key),
        http_requests_per_second=round(requests / 3, 2),
        websockets=sum(float(value) for key, value in after_metrics.items()
                       if key.startswith('vmsh_websocket_connections{')),
    ))
    before_cpu, before_metrics = after_cpu, after_metrics
print(json.dumps(dict(samples=samples), indent=2))
