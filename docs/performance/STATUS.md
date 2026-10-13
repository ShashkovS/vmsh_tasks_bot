# Анализ производительности

## 2026-10-13 — Адресные обновления и scoped SQL

[Утверждённый план](scoped-reads-20261013.md) реализован: адресные ресурсы и очередь refetch ≤4,
scoped отметки/visits, migration 0120 и статистика с RAM TTL ≤60 секунд,
refresh=1 и объединением событий. Memo cell labels сохраняют прежние пороги.
Полный release gate PASS: 3031 Python / 12 SKIP, 1128 frontend, 380 Storybook,
156 E2E / 18 SKIP в Chromium/WebKit/Firefox; format/types/lint/i18n/build PASS,
source_changed=false. Fresh-copy migration/rollback rehearsal и server SQL guard
на обоих production PASS; все 168 business tables сохранили hashes.
TLF `f799f449` выпущен: 25 HTTP, 4 HTML / 116 Staff hashes, services/NATS,
verified backups и business hashes PASS. ВМШ две попытки остановлены до
maintenance/migration из-за сетевого таймаута private sourcemap upload;
deployed revision `aae27430`, службы active. Владелец запросил ремонт штатного механизма: uploader ограничивает размеры
HTTPS-запросов; 65 deploy/static/build PASS и все 406 JS/map bytes сохранены.
Запускается штатный выпуск без proxy/портов. Вечернее сравнение — 19:45 (+03).
Фото/LLM исключены.

## 2026-10-12 — RAM-кеш общих чтений и auth

[Реализовано по решению владельца](worker-read-cache.md): dictionaries в каждом worker,
NATS invalidation, auth TTL до 15 минут и свежие персональные результаты.
HTTP proof: warm auth/me, материалы и список занятий — 0 SQL; задачи — 1 SQL.
Final fast gate PASS: 3012 Python / 12 SKIP, 1119 frontend, 380 Storybook,
43 Chromium auth/content/realtime, types/lint/i18n/build; source unchanged.
[Квитанции и границы проверки](../../pwa_tests/reports/worker-read-cache-20261012/README.md).
13.10 выпущен `f0003fff` на ВМШ/TLF: backend без migrations, frontend сохранён.
По 25 HTTP checks / 4 HTML / 116 Staff hashes PASS; службы active, NRestarts=0,
maintenance off, ошибок старта в просмотренных журналах нет.
[Выпуск и проверки](worker-read-cache-release.md). Новые p95/p99 под нагрузкой ещё не измерены.

- 2026-10-08, Telegram alerts: проверены live Prometheus 3.13.2/Grafana 13.1.1.
  Все 5 targets UP, Prometheus rules/Alertmanager отсутствуют. После 5 октября
  CPU p95 19.6%, выше 80% нет непрерывных двух минут; RAM available 64%,
  root disk available 22.5% (минимум 18.1%). p95 интерактивных routes повторно
  достигает 3–4.5 с при невысоком CPU. Через административный API включены
  [13 правил](../deploy/vmsh-alerting/rules.yml), [Grafana config](../deploy/vmsh-alerting/grafana.json)
  и Telegram contact point `vmsh-telegram`:
  CPU 80/95% 2m, web/monitoring 1m, 5xx 5+ и 5%/5m, p95 1s/3m при 30+ GET,
  read/write queue 20/5 на 30s, loop 5 stalls/5m, RAM 10%/5m, OOM,
  disk 15%/10m и 5%/2m. `promtool check/test` PASS; изолированная Grafana 13.1
  приняла provisioning и API import, routing, проверку сохранённого секрета
  и rollback при неудачной доставке. [Применение](../deploy/vmsh-alerting/apply_api.py)
  создаёт paused rules, тестирует receiver и включает после успешного теста;
  существующие policy tree/resources сохраняются, совпадения UID требуют проверки.
  Production API test Telegram: SUCCESS; в 13:03 UTC все 13 rules enabled,
  health=ok, state=inactive, interval=30s. Группировка instance/severity,
  повторы critical 1h / warning 4h, resolved включены. Grafana и backend
  не перезапускались. Секреты вне Git, исходный env защищён правами 600;
  [helper](../deploy/vmsh-alerting/save_credentials.py) сохраняет новые credentials
  через скрытый ввод. Agent SSH не имеет sudo; использован Grafana API. Полный
  отказ VPS требует внешнего monitor: локальная Grafana не переживёт отказ хоста.

## 2026-10-11 — Переключение GlitchTip

Stage 1 выпущен на оба портала: `e0324272`, миграция 0117 и 25 HTTP checks
на каждом PASS. Stage 2 выпущен: canonical frontend/backend DSN GlitchTip, private release
sourcemaps/CSP и Telegram `@vmsh179bot` в группу ошибок ВМШ. UI/copy/stories не меняются.
[Операционный record](../deploy/glitchtip/migration-20261011.md).

## 2026-10-11 — Квота Sentry 5 000

Владелец разрешил commit/push текущих проверенных правок и выпуск на оба портала,
затем переключение на GlitchTip. [Rollout record](../deploy/glitchtip/migration-20261011.md)
ведёт обе стадии; рабочие серверные данные сохраняются.

[Усиление защиты квоты](2026-10-11-sentry-quota.md) реализовано: бессодержательные
query TypeError, read transport и recovery — breadcrumbs; остальные события
получают общий durable backend admission с отдельными reserves. Custom DSN
caps/error-message filters недоступны в бесплатном Sentry. План: 100 diagnostics
+ 900 важных событий на портал за скользящие 32 дня. Static, 1088 frontend,
364 Storybook, четыре builds и 12 Chromium PASS; после repair 43 quota/HTTP/
schema checks PASS. Остались 6 отсутствующих `_external_pipelines` inputs;
общий gate не зелёный. Correction выпущен на оба портала.

По запросу владельца [GlitchTip 6.2.6](../deploy/glitchtip/README.md) развёрнут
на prep.leaders.tech, https://glitch.leaders.tech. Отдельные VMSH/TLF организации;
HTTPS/IPv4/IPv6, real login, stacks/SDK ingest, restart, backup/restore и renewal
PASS. MCP требует авторизации; retention 30 дней, daily local backups 7 дней.
DSN переключены; Telegram delivery PASS, SMTP выключен по решению владельца.

## 2026-10-10 — Шум frontend Sentry

Реализован [инкремент нормализации](2026-10-10-sentry-noise.md): подтверждённые
штатные отказы, recovery breadcrumbs, semantic grouping и отдельные
client budgets для повторных diagnostics/ошибок.
Sentry MCP подключён: последние 7 дней — 27 357 events, сутки — 3 528.
Все static checks и 1078 frontend PASS; Storybook 363+1 PASS,
Chromium submissions/redeploy/offline-current 12/12 PASS. Approved corpus
восстановлен по SHA; 8 прежних Python failures PASS, остаются 6 missing
`_external_pipelines` inputs. Общий gate не зелёный. По свежим данным добавлен
metadata correction реальных query families и безопасных original stack
locations: focused static checks, 23 unit и 4 Chromium E2E PASS;
все приложения пересобраны. Причина historical TypeError ещё требует нового
representative event после выпуска. Production не менялся.

## 2026-10-08 — Объединённый выпуск

Оба production обновлены 8 октября до `d4bf4a30`: все четыре работы,
миграции 0114–0116 и исправление offline resync выпущены вместе.
На каждом портале 25 публичных HTTP проверок PASS; схема current, сервисы active,
maintenance снят, резервные копии проверены. Внешние JS/CSS/worker bytes и
production provenance совпадают со сборками; CSP разрешает нужные media origins.
На ВМШ старых URL в presentation fields осталось 0; SHA-256 обновлённых
228 derivatives и 41 publication HTML корректны. На TLF все прежние product
rows и credentials сохранены, NATS не перезапускался; migrations up/down/up PASS.

Владелец явно выбрал выпуск по завершённым проверкам после сообщения об
оставшихся browser failures. **Общий release gate не считается зелёным**:
2882 Python / 7 SKIP, 1068 frontend, 364 Storybook PASS; основная E2E-фаза
385 PASS / 20 SKIP / 6 FAIL, затем focused regressions PASS. Финальные
figure/runtime/statistics/visual и полный locale replay остаются follow-up
после разгрузки тестового Mac. Direct S3 не включён: browser WebP идёт через
лёгкий backend proxy без повторного кодирования. Production ускорение ещё не измерено.

[Состав, решение владельца и квитанции](integrated-release-20261008.md).

- 2026-10-08, исправления: реализован [инкремент](2026-10-08-fixes.md).
  Индекс 0114 сократил пустую push selection 164–190 → 32–36 мс на одной
  временной копии production DB; VM-step regression и rollback/apply проходят.
  TLF: 1114/1120 nginx503 относятся к p-45/46/49 с SELECT_ONE без вариантов;
  metadata review и publication gate теперь проверяют тот же input, что Student.
  Клиентские online/WS resync объединены, bounded до четырёх active queries;
  controlled offline/recovery query errors не повторяются и не попадают
  в Sentry; необъяснённый AbortError остаётся видимым, реальные failures имеют
  безопасные family/kind. Python 2847 PASS / 6 SKIP, frontend 1055 PASS, Storybook 363 PASS;
  format/types/lint/i18n PASS. Auth/realtime/redeploy/offline-current/content/
  submissions: 139 PASS / 20 штатных SKIP в трёх браузерах; retries=0. CPU correction и photo flow
  исключены. Production не изменён.

Дополнительный correction: refresh response переживает reload благодаря
keepalive на auth/refresh. Private-reload regression: 9/9 (три повтора в
Chromium/WebKit/Firefox); общая браузерная матрица: 139 PASS / 20 штатных SKIP в трёх браузерах.

- 2026-10-08: завершён read-only аудит обоих production порталов и Telegram с
  03.10 00:00 до 08.10 10:05 (Asia/Nicosia). [Отчёт](2026-10-08-analysis.md),
  [ВМШ metrics](2026-10-08-vmsh-prometheus.json),
  [TLF metrics](2026-10-08-tlf-prometheus.json), [Sentry](2026-10-08-sentry.json).
  CPU correction `bdfcf9a2` снизил p95 задач 9,66 с → 429 мс, однако read
  bursts 6–7 октября достигают 161/102 queued reads у одного worker и
  3,7–4,4 с локального p95. Media: 135 ВМШ HTTP503 преимущественно 04.10;
  TLF: ≈1111 test-input HTTP503 04.10 10–11 UTC. Sentry: 22 929 принятых
  PWA событий и существенный backoff/spike-protection; counts не означают
  потерянные ответы. Старый `client:UnknownError` 26.09 разобран как отдельная
  гипотеза local outbox/IndexedDB, без установленной первопричины.
  Все Prometheus queries успешны, дневные Sentry totals сверены с общим;
  raw journals остаются вне Git. Follow-up: владельцы read slots, media
  transport classification, TLF configuration/repository failure, client
  stage diagnostics и alert rules. Runtime/production данные не менялись;
  исторический journal ВМШ закрыт, TLF journal покрывает только 7–8 октября.

- 2026-09-27: read-only аудит завершён. [Отчёт](2026-09-27-analysis.md),
  [агрегаты Prometheus](2026-09-27-prometheus.json),
  [маршруты](2026-09-27-routes.csv),
  [запросы для повторения](2026-09-27-prometheus-query.py).
- Выполнены: ресурсы → HTTP/SQLite метрики → доступные journald/Sentry → код →
  приоритеты. Production и пользовательские изменения не менялись.
- Подтверждены: секундные uploads, эпизодическая read admission queue,
  106 HTTP 500 reveal за измеренное окно. Нет устойчивого насыщения сервера.
- Follow-up: stacktrace reveal; диагностика отсутствия свежих Sentry событий;
  полный журнал burst с владельцами слотов; stage timings конверсии/storage;
  изолированный benchmark вариантов readers и reconnect fan-out.
- Ограничения: SSH разрешает последние 100 строк journald, nginx access.log
  недоступен; текущий фрагмент совпал с deployment. Историческую первопричину
  очередей и разбивку upload времени нельзя подтвердить имеющимися данными.

- 2026-09-27, follow-up: по решению пользователя убран повторный SHA256 при
  выдаче письменных фото всем аудиториям в `written_submission_routes.py`.
  Проверки доступа, размера/type и upload validation сохранены. Выполняется
  проверка существующих HTTP сценариев; S3 GET и кеширование не меняются.
- Проверка удаления read-time SHA256: 7 существующих HTTP тестов written/
  attachment прошли, включая student/family/staff и отказ без авторизации.
  Первый запуск был заблокирован sandbox на bind локального сокета; повтор с
  разрешёнными локальными сокетами успешен. `git diff --check` прошёл.
- Следующее обсуждаемое улучшение: прямая выдача обработанных фото из S3 по
  короткоживущим подписанным URL после проверки доступа; ещё не реализовано.
- 2026-09-27: реализуется [прямая выдача фото](photo-delivery.md) через 302 на
  S3 URL с TTL 86400 по решению пользователя. Stable mediaPath обновляет ссылку
  при повторном запросе; backend не читает объект. Проверяются signing и HTTP.
- Gate пройден: 32 теста S3/written HTTP PASS, `git diff --check` PASS.
  Read-only проверка production nginx: bucket origin Beget уже разрешён в
  img-src/connect-src. Сервер и bucket не изменялись; нужен обычный backend release.

- 2026-09-27 incident: production 34af1445 включает unconditional photo 302.
  Найдена несовместимость: WrittenMaterialReassignmentClient и
  WrittenSubmissionClient используют Blob fetch с redirect:error. Это упущено
  в исходной проверке. Hotfix: S3 redirect только для Sec-Fetch-Dest:image,
  Sec-Fetch-Mode:no-cors; fetch/CORS/старые клиенты снова получают 200 с байтами.
  Повторное SHA256 не возвращается. Выполняется HTTP regression перед выпуском.

- Incident hotfix gate: 32 S3/written HTTP PASS, diff-check PASS; готов к
  выпуску. Проверка deployment и возврата media 200 выполняется после push.
- Hotfix 2504acb0 отправлен и выпущен 27.09 в 12:52:52 UTC. Deploy log:
  frontend=false, backend=true, migrations=false; все runtime/ready и metrics
  health checks PASS, service active, NRestarts=0. Frontend symlink остаётся
  на 34af1445: это ожидаемый backend-only выпуск. Пользовательский browser smoke
  пока не подтверждён; интерфейс нужно обновить для повторной загрузки фото.

- 2026-09-28: завершена read-only [проверка перед нагрузкой](2026-09-28-readiness.md).
  [18h baseline](2026-09-28-baseline.json) сохранён. Обычные API p95 88–175 мс,
  очередь read peak 23/worker, устойчивого насыщения ресурсов нет. Reveal всё
  ещё даёт 59 HTTP 500 за окно. Prometheus rules пусты; доступ к полному journald
  остаётся главным ограничением вечернего анализа. Новые metrics/alerts и
  изменения runtime не выкатывались; предложения и границы проверки в отчёте.
- 2026-09-28 instrumentation increment: media stages с фиксированными labels,
  loop lag histogram/live worker gauge и rate-limited frontend failure event
  через существующую аналитику. Без payload/URL, без дополнительного Sentry,
  без новых фоновых таймеров. Проверки и подготовка экспорта журнала выполняются.

- Instrumentation gate: 147 Python и 23 frontend tests PASS, ESLint/typecheck PASS.
  [Документация](2026-09-28-instrumentation.md), alert rules (promtool PASS) и
  exporter (bash -n PASS) подготовлены; alerts/export не активированы.
- Vite production builds staff/student/family PASS (предупреждения о размере chunks).
- Выпущен a08bc163: 28.09 08:58 UTC, frontend/backend, без migrations.
  Все deploy health checks PASS; NRestarts=0. Новые loop metrics доступны
  в production у обоих workers (после старта текущий lag 0.7–0.9 мс).
  Browser failure события появятся после обновления клиентов и реальных ошибок;
  их end-to-end приём проверен тестами, production ошибки не провоцировались.

- 2026-09-28 evening audit: анализ окна 13:38–16:38 UTC по Prometheus,
  новым media/loop metrics и Sentry; runtime не меняется. Уточняются короткие
  DB queue spikes и клиентские TypeError; полный журнал окна пока недоступен.
- Evening audit завершён: [отчёт](2026-09-28-peak-analysis.md), raw Prometheus сохранён.
  93k HTTP, 0,294% >1s, 6 HTTP500; короткий admission burst, upload convert ~81%.
  Sentry query errors массовые, их первопричина скрыта текущей sanitization.
  Runtime не менялся; полный journal и transport classification остаются follow-up.

- 2026-10-08: начата реализация браузерного WebP/direct-to-S3 для всех пользовательских фото; решение: [browser-image-uploads](browser-image-uploads.md). Протокол/миграция, черновики и release gate в работе.

- 2026-10-08: протокол, все photo endpoints, общий worker и durable metadata подключены; initial 95 Python checks и workspace typecheck PASS. Убран повторный Rich Markdown GET/convert при сохранении. Release gate запускается; provider/browser proof ещё не подтверждён.

- 2026-10-08: pinned live Beget probe подтвердил несовместимость SHA-256 (изменённый PUT принят, HEAD checksum отсутствует); cleanup ACK PASS. Direct flag остаётся выключенным; подготовленный WebP использует лёгкий proxy. Первый release gate остановился на format, исправлено; повтор в работе.
- 2026-10-08: Python 2863/7 SKIP, frontend 1053, Storybook 364 PASS. E2E выявил преждевременный saved indicator при подготовке нового фото; исправлено, добавлена native-worker проверка EXIF/форматов и 1/2/10 фото. Незавершённый release run прерван для проверки исправления; финальная квитанция pending.
- Окончательный код: 2867 Python / 7 SKIP, 1054 frontend, 364 Storybook PASS; целевые photo/dialogue E2E 15 PASS. В общем release gate Chromium/WebKit прошли основной прогон, Firefox и завершающие фазы в работе. [Браузерные замеры](../../pwa_tests/reports/browser-image-uploads-20261008/README.md).
- Реализация завершена. Финальные relevant-mode проверки: все prep suites и 63 функциональных E2E в трёх браузерах PASS; Staff visual 3 PASS, Student visual 3 FAIL из-за добавленного курса в тестовой фикстуре. Различия осмотрены, эталонные снимки сохранены. Default all-mode gate не зелёный: 6 сбоев в сценариях navigation/refresh/SW. [Итоговый отчёт](../../pwa_tests/reports/browser-image-uploads-20261008/README.md). Direct flag выключен после несовместимого Beget proof; production не менялся.
