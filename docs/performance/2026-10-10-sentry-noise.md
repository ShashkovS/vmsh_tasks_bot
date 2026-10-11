# Нормализация frontend Sentry — 10 октября 2026

Политика этого инкремента уточнена [11 октября для квоты 5 000](2026-10-11-sentry-quota.md):
shared backend admission вместо одного per-tab лимита; read transport/recovery
и source-less query TypeError остаются breadcrumbs. Числа ниже — история проверки v1.

## Основание и план

Запрос владельца: десятки тысяч frontend событий расходуют квоту и скрывают
полезные ошибки. [Последний сохранённый аудит](2026-10-08-analysis.md#sentry-и-отправка-ответов)
за 3–8 октября: 22 929 принятых событий, 14 864 query TypeError, 1 720
query AbortError, 1 410 query API failures; ещё есть короткие service recovery
episodes и штатные auth/domain отказы. Это исторический baseline, не свежие
данные после выпуска `d4bf4a30`. Свежие данные проверены через Sentry MCP
после штатного OAuth-подключения по запросу владельца.

## Свежая проверка Sentry

Снимок около 10 октября 21:51 Asia/Nicosia через Sentry MCP, `vmshpwa`:

| Окно | Принятые search events | Различные user IDs |
| --- | ---: | ---: |
| Последние 7 суток | 27 357 | 733 |
| Последние 24 часа | 3 528 | 327 |

[7-day query](https://shashkovs.sentry.io/explore/discover/homepage/?dataset=errors&queryDataset=error-events&project=4511885728088064&field=count%28%29&statsPeriod=7d&mode=aggregate).
За 7 дней: 18 171 query TypeError, 1 766 AbortError, 1 671 query API failures,
1 257 AuthNetworkError, 867 CourseNetworkError. За сутки последний release
`d4bf4a30ce9d-20261008155618` даёт 2 595 `query TypeError / unknown / other`,
163 oral 404 `oral_window_not_found`, 62 auth 401 `authentication_required`,
35 `session_revoked`, 22 `test_attempt_hour_limit` и 4 day limit.
[Свежая разбивка](https://shashkovs.sentry.io/explore/discover/homepage/?dataset=errors&queryDataset=error-events&project=4511885728088064&field=title&field=operation&field=query_family&field=transport_kind&field=http_status&field=api_code&field=release&field=count%28%29&sort=-count%28%29&statsPeriod=24h&mode=aggregate).

[VMSHPWA-52](https://shashkovs.sentry.io/issues/VMSHPWA-52) подтверждает synthetic
capture stack вместо исходной причины. Поэтому unknown TypeError нельзя
объявить сетевым и sampled только по имени. Основной поток — Student;
2 065 событий последнего release за сутки приходятся на `/student/tasks`.
`Uy` также относится к существующему recovery issue
[VMSHPWA-55](https://shashkovs.sentry.io/issues/VMSHPWA-55), 107 за сутки.

Daily outcomes за 7 дней: 11 574 `ratelimit_backoff`, 1 938 `spike_protection`,
1 626 `network_error`, 23 085 `event_processor`. Эти bucketed данные не
равны уникальным ошибкам и не складываются с search counts; daily boundaries
могут включать часть суток вне rolling search window.
За последние сутки hourly outcomes: accepted 3 528, `event_processor` 2 954,
`network_error` 160; quota/spike drops за это окно не обнаружены.
[Сохранённые агрегаты без event payload/user data](2026-10-10-sentry.json).

Реализованная политика:

1. В [reportHandledError](../../vmshpwa/packages/app-shell/src/observability.ts)
   исключить только подтверждённые ожидаемые пары HTTP status/code для чтения
   и отказов по сроку/лимиту попыток. Не скрывать произвольные 4xx/5xx,
   TypeError, неизвестные AbortError и ошибки локального хранения.
2. Короткие recovery episodes оставить breadcrumbs; warning только после
   существующего 60-секундного prolonged threshold.
3. В общем SDK `beforeSend` ограничить повторные события и разделить бюджеты
   диагностических чтений, prolonged recovery и остальных ошибок. Выборочно
   отправлять только типизированные network/deadline failures чтения.
4. Группировать известные API/transport failures по безопасной семантике,
   независимо от stack места capture, user/problem/request ID и release.
   Неизвестные bugs дополнительно различать по безопасной исходной location.
   Реальные contracts keys `oral-windows`, `offline-lessons`, `home` и другие
   имеют bounded aliases в [queryFamily](../../vmshpwa/packages/app-shell/src/query-errors.ts).
   Без этого подтверждённые oral 404 ошибочно получали family=other.
   Безопасный original stack сохраняет только same-origin public app `.js`
   locations, включая глубочайший доступный cause; messages/function names,
   credentials/query/hash, API/media/third-party URLs исключены.
5. Регрессии фильтрации/бурстов/сохранения неожиданных ошибок и один
   `make pwa-check-fast PWA_E2E_MODES="submissions redeploy offline-current"`.

Изменение касается telemetry всех трёх аудиторий. Доставка ответов, outbox,
retry policy и UI не меняются; миграции не нужны. Общий `sampleRate` не
снижается. Первая неизвестная ошибка каждой сигнатуры сохраняется в рамках
отдельного бюджета; network read diagnostics могут быть sampled.
Лимиты клиентские, на документ: reload/другая вкладка получают новый бюджет.
Они не задают жёсткую общую квоту проекта Sentry.

## Политика SDK

Общий [createSentryEventFilter](../../vmshpwa/packages/app-shell/src/sentry-noise.ts)
подключён в `initFrontendObservability` до privacy sanitizer. Он покрывает
ручные и автоматические capture. `mechanism.handled=false` направляет событие
в бюджет ошибок независимо от query tag.
Стандартный SDK Dedupe заменён этим limiter: он иначе подавляет последовательные
одинаковые события до sampling и без временного окна. Остальные default
integrations сохранены, включая GlobalHandlers.

| Поток | Максимум за 15 минут на документ | Повтор той же сигнатуры | Sampling |
| --- | ---: | --- | --- |
| Handled query diagnostics | 6 | раз в 15 минут | network/deadline 10%; остальные 100% |
| Prolonged service recovery | 1 | раз в 15 минут | 100% |
| Отправка, storage, неожиданные/автоматические ошибки | 20 | раз в минуту | 100% |

Sampling применяется только при `operation=query` и типизированном
`transport_kind=network/deadline`. Неизвестный TypeError не считается сетевым.
Короткие reconnect/update episodes остаются breadcrumbs; prolonged warning
использует уже существующий threshold 60 секунд из contracts transport.
Первые отдельные неожиданные ошибки сохраняются, пока не исчерпан их бюджет.
События содержат `telemetry_policy=frontend-v1` и `extra.telemetry`: sampleRate,
лимиты и число подавленных вызовов фильтра с прошлого принятого события.
Это диагностика client filtering, не полный глобальный failure counter;
Sentry SDK/transport и сервер могут дополнительно отбросить события.

Ручные fingerprints содержат operation/family/kind/type/status/code;
user/problem/outbox/request ID не разделяют группы. Для unknown failures
добавляется первая безопасная исходная app location: разные программные ошибки
не склеиваются только из-за TypeError. Эта location может измениться после
новой minified сборки; API/typed transport группы не зависят от capture stack.
Для автоматических ошибок стандартная Sentry grouping сохраняется; локальный limiter различает
type/message/stack location, хранит только hash и счётчики, максимум 128
сигнатур. Reload не сохраняет hash/счётчики в browser storage.

Штатные отказы проверяются по точным парам, а не по одному status:
query 401 `authentication_required/session_revoked`; oral query 404
`oral_window_not_found`; submission/mutation 409 `submission_deadline_passed`,
422/429 `test_attempt_hour_limit/test_attempt_day_limit`. Несоответствующие
status, семейство или операция остаются видимыми; auth failure при отправке
сохраняется. Existing service controls подавляются только при status 503.

Регрессии: [sentry-noise.test.ts](../../vmshpwa/packages/app-shell/src/sentry-noise.test.ts)
(10 000 repeats, unique floods, budgets, sampling, window reset),
[observability-init.test.ts](../../vmshpwa/packages/app-shell/src/observability-init.test.ts)
(disabled DSN, real init hook, privacy, prolonged reporter),
[query-errors.test.ts](../../vmshpwa/packages/app-shell/src/query-errors.test.ts)
(реальные contracts keys, semantic fingerprints, expected refusals,
retained HTTP failures, безопасные original locations и разные unknown bugs).

## Проверка и follow-up

[Сохранённый отчёт проверки](../../pwa_tests/reports/sentry-noise-20261010/validation.json)
фиксирует команды, результаты, digest финальных исходников и шесть missing-input failures.

Реализация завершена; все статические фазы gate PASS. Python import сначала
остановился из-за отсутствующего локального test-profile в свежем checkout.
Создан игнорируемый isolated profile без Telegram/Google/Sentry credentials;
оставшиеся фазы выполняются без повторения пройденных проверок.
Frontend **1078 PASS**, включая 10 новых regressions. Python исходно **2867
PASS / 8 SKIP / 14 FAIL** из-за отсутствующих local inputs. Восстановлены 54
non-personal `_vmsh_examples` файла из основного checkout; все SHA совпали с
committed manifest. Повторены только 8 упавших corpus checks — PASS;
остаются 6 failures отсутствующего `_external_pipelines`, backend не менялся.
Storybook 363 PASS + missing-corpus story 1 PASS после восстановления PDFs.
Chromium `submissions redeploy offline-current`: **12/12 PASS**, все четыре
production-profile verification builds PASS. Общий gate не зелёный.
Свежие Sentry данные привели к дополнительному metadata correction
(реальные family aliases и safe original locations); его focused static/unit/
offline-current verification: format/types/lint, **23/23 unit** и **4/4
Chromium E2E PASS**, все четыре приложения пересобраны. Stack regression
покрывает также Firefox/Safari syntax; browser acceptance запущен в Chromium.
Ранее пройденные unaffected suites не повторяются. Receipts:
`.runtime/vmshpwa/checks/20261010T183207.199632Z/summary.json` и
`continued.json`, `corpus-resumed.json` и `metadata-final.json`;
первые type/format/lint findings исправлены, исходные
неуспешные receipts сохранены. После выпуска сравнить одинаковые временные окна
по release, audience, operation, query_family, transport_kind и Sentry
outcomes. Отсутствие событий после client filtering не доказывает устранение
пользовательского сбоя; HTTP/SQLite/media метрики остаются источником объёмов.
Первопричина исторических untyped TypeError не установлена этим инкрементом:
после выпуска нужен representative event с исходной location новой версии.
Production этим инкрементом не изменён.
