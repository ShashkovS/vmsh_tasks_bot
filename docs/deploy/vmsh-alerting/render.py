"""Render reviewed rules for Grafana 13.1; docs/performance/STATUS.md, 8 October.

Telegram credentials are placeholders; apply_api.py injects them in memory.
The generated provisioning touches only these rules/contact point, not the
policy tree or other Grafana resources. Run locally with the repository uv runtime.
"""

import argparse
import json
from pathlib import Path

import yaml


def render(source):
    rules = []
    for group in source["groups"]:
        for rule in group["rules"]:
            critical = rule["labels"]["severity"] == "critical"
            rules.append({
                "uid": "vmsh-health-" + rule["alert"].removeprefix("Vmsh").lower(),
                "title": rule["alert"],
                "condition": "B",
                "data": [
                    {"refId": "A", "datasourceUid": "prometheus",
                     "relativeTimeRange": {"from": 600, "to": 0},
                     "model": {"refId": "A", "expr": f'({rule["expr"].strip()}) * 0 + 1',
                               "instant": True, "range": False,
                               "intervalMs": 1000, "maxDataPoints": 43200}},
                    {"refId": "B", "datasourceUid": "__expr__",
                     "relativeTimeRange": {"from": 0, "to": 0},
                     "model": {"refId": "B", "type": "threshold", "expression": "A",
                               "conditions": [{"type": "query",
                                               "query": {"params": ["B"]},
                                               "reducer": {"type": "last", "params": []},
                                               "evaluator": {"type": "gt", "params": [0]},
                                               "operator": {"type": "and"}}]}},
                ],
                # Empty filtered vectors mean healthy, including idle routes.
                # Normalize presence above: bad raw values may be zero (up/disk).
                "noDataState": "OK",
                "execErrState": "Alerting" if rule["alert"] == "VmshMonitoringUnavailable" else "KeepLast",
                "for": rule["for"],
                "keepFiringFor": "1m",
                "isPaused": False,
                "labels": {**rule["labels"], "instance": "vmsh.shashkovs.ru", "service": "vmsh"},
                "annotations": rule["annotations"],
                "notification_settings": {
                    "receiver": "vmsh-telegram",
                    "group_by": ["instance", "severity"],
                    "group_wait": "10s" if critical else "30s",
                    "group_interval": "5m",
                    "repeat_interval": "1h" if critical else "4h",
                },
            })
    return {
        "apiVersion": 1,
        "contactPoints": [{
            "orgId": 1, "name": "vmsh-telegram",
            "receivers": [{
                "uid": "vmsh-health-telegram", "type": "telegram",
                "disableResolveMessage": False,
                "settings": {
                    "bottoken": "$VMSH_ALERT_BOT_TOKEN",
                    "chatid": "$VMSH_ALERT_CHAT_ID",
                    "message": (
                        'ВМШ — {{ if eq .Status "firing" }}проблема{{ else }}восстановлено{{ end }}\n'
                        '{{ range .Alerts.Firing }}⚠ {{ .Annotations.summary }}\n'
                        '{{ if .Labels.route }}{{ .Labels.route }}\n{{ end }}'
                        '{{ if .Labels.role }}SQLite: {{ .Labels.role }}\n{{ end }}'
                        '{{ if .Labels.job }}Job: {{ .Labels.job }}\n{{ end }}{{ end }}'
                        '{{ range .Alerts.Resolved }}✅ {{ .Annotations.summary }}\n{{ end }}'
                        'Графики: https://grafvmsh.shashkovs.ru/'
                    ),
                },
            }],
        }],
        "groups": [{"orgId": 1, "name": "vmsh-production", "folder": "VMSh Alerts",
                    "interval": "30s", "rules": rules}],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source = yaml.safe_load(Path(__file__).with_name("rules.yml").read_text())
    args.output.write_text(json.dumps(render(source), ensure_ascii=False, indent=2) + "\n")
