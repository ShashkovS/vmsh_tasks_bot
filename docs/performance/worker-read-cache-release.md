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

Приложение `f0003fff8028e77a32270e5353f9780a44f692c3` выпущено на оба портала
13.10: ВМШ PWA поднят в 05:41:24 UTC, TLF в 05:41:32 UTC
(08:41 Asia/Nicosia). На ВМШ deploy marker обновлён, webhook завершился:
`frontend=false backend=true migrations=false`. На TLF release record:
`/web/vmsh_tasks_bot/deploy/releases/tlfprep-20261013-worker-cache-f0003fff8028/`.

На каждом: 25 публичных HTTP checks PASS, NATS ready, 4 HTML и 116 Staff
JS/CSS SHA-256 совпали; прежние production provenance/static release сохранены,
public sourcemaps отсутствуют, anonymous media 401. Службы active,
NRestarts=0, maintenance off. В просмотренных startup/post-deploy журналах
PWA и Telegram/Zoom нет Traceback/error/failed-boot signatures; по два PWA worker
поднялись. Обезличенная [квитанция](../../pwa_tests/reports/worker-read-cache-20261012/production-proof.json).

TLF: stopped-writer SHA-256 comparison сохранил 168 таблиц / 38 207 строк;
полные config/env hashes совпали, NATS PID 1093 прежний. Проверенные backups
до/после: `20261013T054129.001103Z` / `20261013T054134.412311Z`, restore integrity ok.
ВМШ: live SQLite read-only quick_check ok, NATS PID 1409 прежний.
Приложение/схема/credentials не менялись при последующем сохранении этого record;
документацию можно fast-forward без рестарта и пересборки.

Production p95/p99 пока не измерены; короткий smoke не доказывает эффект
в вечернее окно. Следующий замер — на естественной нагрузке.
