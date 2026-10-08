# Production Prometheus instrumentation — proof, 11 August 2026

## Scope and traceability

- Aiohttp instrumentation: [`helpers/prometheus_metrics.py`](../../helpers/prometheus_metrics.py).
- Outermost app-factory installation: [`main.py`](../../main.py).
- PWA/legacy WebSocket lifetime integration: [`apps/pwa_app.py`](../../apps/pwa_app.py),
  [`apps/online_app.py`](../../apps/online_app.py),
  [`apps/game_web_app.py`](../../apps/game_web_app.py).
- Gunicorn dead-worker hook: [`gunicorn.conf.py`](../../gunicorn.conf.py).
- Production multiprocess/dual-listener unit:
  [`vmshpwa.service.template`](../../vmshpwa/deploy/systemd/vmshpwa.service.template).
- Public scrape denial: [`vmshpwa.conf.template`](../../vmshpwa/deploy/nginx/vmshpwa.conf.template).
- Runtime tests: [`test_prometheus_metrics.py`](../test_prometheus_metrics.py),
  [`test_gunicorn_config.py`](../test_gunicorn_config.py), plus systemd/nginx
  structural tests.

The canonical Nginx upstream remains the existing Unix socket. The same two
PWA Gunicorn workers additionally listen on `127.0.0.1:8000` solely for local
Prometheus scrapes. No extra exporter or application process was introduced.

## Automated evidence

- Prometheus/Gunicorn/systemd/nginx/app-factory/PWA focus: **94 passed**.
- Legacy Python suite: **123 passed / 2 skipped**.
- Full PWA Python suite after the instrumentation fix: **1680 passed / 6
  skipped / 1 unrelated pre-existing migration failure**. The remaining test
  independently fails because a Phase-9 migration attempts to rename absent
  `student_lesson_metrics`; no observability file participates in that path.
- Ruff format/check on new instrumentation, deployment checkers and tests:
  **pass**.
- Frontend ESLint/Stylelint: **pass**; strict TypeScript: **pass**; four-app
  production build: **pass**.
- Frontend unit baseline remains red on **11 unrelated existing tests** in
  auth/session/realtime and Student search validation. Frontend source was not
  changed by this increment.
- Workspace Prettier check reports **12 existing files** outside this change;
  no global write was performed.
- `git diff --check`: **pass**.

## Production gate

Not run locally as production: the rendered systemd unit and installed Nginx
configuration must be updated first. Deployment proof requires:

1. systemd-created `/run/vmsh-prometheus` and exact two-worker dual bind;
2. local `http://127.0.0.1:8000/metrics` exposition;
3. public `https://vmsh.shashkovs.ru/metrics` returning `404`;
4. exact `/etc/prometheus/targets/aiohttp.json` target and Prometheus target UP;
5. Grafana queries returning the four fixed `vmsh_*` metric families.
