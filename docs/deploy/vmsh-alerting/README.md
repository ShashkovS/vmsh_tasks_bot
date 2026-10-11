# VMSh production alerts

The owner approved and enabled these 13 Grafana rules on 2026-10-08.
All rules were enabled with healthy/inactive evaluation after the existing
Telegram receiver passed its operator-authorized test. No backend/Grafana
restart was required. See [performance status](../../performance/STATUS.md)
and the [2026-10-11 release audit](../release-audit-20261011.md).

[`rules.yml`](rules.yml) and [`rules.test.yml`](rules.test.yml) define and test
the conditions. [`render.py`](render.py) generates [`grafana.json`](grafana.json);
[`apply_api.py`](apply_api.py) defaults to read-only preflight. Its explicit
`--apply` mode preserves existing resources/policy, creates paused rules, tests
the receiver, then enables them. Do not repeat installation during application
deployments. [`save_credentials.py`](save_credentials.py) uses hidden input;
credentials and private provisioning inputs stay outside Git.

Local Grafana cannot signal total failure of its own VPS; external monitoring
remains a separate follow-up. Thresholds, notification policy and receiver are
unchanged by committing these previously deployed source artifacts.
