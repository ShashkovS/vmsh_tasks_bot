# Выпуск RAM-кеша — 13 октября 2026

Владелец разрешил выпуск [проверенного кеша](worker-read-cache.md) на ВМШ и TLF.
[Fast gate](../../pwa_tests/reports/worker-read-cache-20261012/README.md):
3012 Python / 12 SKIP, 1119 frontend, 380 Storybook, 43 Chromium PASS.
Код после gate не менялся. Миграций и новых зависимостей нет.

Перед выпуском оба checkout: `cf694104ca3272b824f5334348d0ce0ca1d90af4`,
tracked clean. Существующие untracked backups/config records сохраняются.
PWA и Telegram/Zoom active, NRestarts=0; NATS PID ВМШ 1409, TLF 1093.
Свободно ВМШ 11 GiB, TLF 67 GiB.

ВМШ: штатный signed GitHub webhook production-ветки `vmshpwa`.
TLF: [backend deploy](../../pwa_tests/reports/worker-read-cache-20261012/deploy-tlf.sh)
на основе предыдущего проверенного release: safety backup/restore integrity,
stopped-writer comparison всех product tables, config hash, NATS PID,
runtime/public HTTP. При ошибке возвращает прежний код без отката данных.
Static release, credentials, schema, NATS и установленные backup timers сохраняются.
Файлы TLF находятся под `/web/vmsh_tasks_bot/deploy/releases/`.

Выпуск в работе. Production p95/p99 пока не измерены; короткий smoke не
доказывает эффект в вечернее окно. Следующий замер — на естественной нагрузке.
