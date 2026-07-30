# Аудит выполнения плана разработки — 30 июля 2026 года

Этот отчёт сверяет не отметки в `STATUS.md`, а фактически существующие
миграции, HTTP-маршруты, страницы, тесты и proof-отчёты. Наличие файла или
Storybook-прототипа само по себе не считается завершением этапа.

Проверенная ревизия: `c8ae81a`.

Последний полный автоматический checkpoint этой ревизии:

- frontend unit: 102 файла, 561 тест;
- Python PWA: 1474 passed, 5 skipped;
- линтеры, strict TypeScript и production builds ранее прошли в том же
  Phase-11 цикле;
- Student и Family собирают отдельные `injectManifest` service workers;
- полный production-build Playwright: 197 passed, 6 skipped, 4 failed;
  три падения — непринятый новый Student visual baseline, одно — нестабильный
  Firefox-сценарий публикации;
- изолированный realtime-набор: 12/12 passed;
- двухпроцессный smoke на общей WAL SQLite и NATS: 40/40 login writes, без
  `SQLITE_BUSY` и half-write.

## Как читать статусы

- **Функционально готов** — основной пользовательский путь существует в
  настоящих приложениях и проходит API/browser tests, но у этапа ещё может быть
  ручной или production gate.
- **Частично готов** — полезные вертикальные срезы работают, но заявленный в
  phase-файле пользовательский результат ещё неполон.
- **Внешний gate** — результат нельзя честно получить только локальным кодом:
  нужен production config, решение владельца или ручное визуальное принятие.

## Сводка по этапам

### Phase 0 — baseline: частично принят

Работают изолированные human/agent profiles, воспроизводимые seed/schema/golden
checks, app factory без Telegram/Google, filesystem storage, локальные
converter probes, NATS и разрешённые test-S3/test-Telegram smokes. Есть
численный профиль реальных event logs и отдельный двухворкерный write burst.

Осталось:

- принять или отклонить новые visual baselines;
- измерить именно фото/outbox workload и зафиксировать простой допустимый
  `SQLITE_BUSY` budget; текущие 40 логинов этого не доказывают;
- зафиксировать финального владельца acceptance.

Основные доказательства: [baseline](baseline-v1.md),
[runtime isolation](runtime-isolation-phase0.md),
[live integrations](phase0-live-integration-2026-07-27.md),
[two-worker workload](phase11-two-worker-runtime.md).

### Phase 1 — identity/access: функционально готов, production activation открыт

Реализованы audience-scoped cookie sessions, refresh/revoke/device list,
Student/Family/Staff login, Family-child authorization, Staff scopes,
authenticated WebSocket и trusted-proxy boundary. Browser-auth работает во
всех трёх движках.

Осталось:

- owner-only решение по 10 блокирующим legacy rows и 29 collision groups из
  вопроса 16;
- controlled production import/apply;
- nginx/FQDN smoke на целевом сервере;
- ручное визуальное принятие login/session/forbidden состояний.

Доказательства: [preflight](auth-preflight.md),
[import tooling](phase1-auth-import-tooling.md),
[race hardening](phase1-auth-race-hardening.md), Phase-1 разделы
`vmshpwa/dev/development-plan/05-phase-1-auth.md`.

### Phase 2 — content/publication: функционально готов, production data gate открыт

Работают TeX compiler, browser/Telegram/PDF derivatives, TikZ/SVG и raster/WebP,
asset matching, metadata review, bulk upload, независимые condition/hint/
solution schedules, publication/rollback и трёхбраузерный Student read flow.

Осталось:

- owner-reviewed mapping и rehearsal/apply истории занятий 1–38 на отдельной
  production-копии;
- ответ на вопрос 17 о смысле schedule anchor;
- визуальное принятие реальных content screens.

Доказательства: [compiler](phase2-content-compiler.md),
[real corpus](phase2-real-content-corpus.md),
[content E2E](phase2-content-e2e.md),
[history backfill tooling](phase2-content-history-backfill.md).

### Phase 3 — Student reading/offline: функционально готов

Работают course/group access, home и archive list, focused/long task,
publication reveal, KaTeX/SVG renderer, owner-isolated IndexedDB cache и
cold-offline reading. Остался только ручной visual gate.

Доказательства: [course access](phase3-course-access-api.md),
[problem list](phase3-student-problem-list.md),
[offline reading](phase3-student-offline-reading.md),
[long math](phase3-long-math-rendering.md).

### Phase 4 — test submissions: функционально готов

Все 23 legacy answer types, contextual validation, limits, immediate verdict,
idempotency, deadline/client-time audit, local draft/outbox, retry и Staff
recheck подключены к реальному Student flow. Telegram использует ту же policy.
Остался ручной visual gate.

Доказательство: [test submission vertical](phase4-test-submission-domain-and-repository.md).

### Phase 5 — written submissions: функционально готов с media edge gap

Работают client WebP worker, server fallback, 1–10 фото, preview/reorder,
reload-safe Dexie outbox, atomic submit/replacement, immutable reviewed
evidence, Staff media access, reassignment и настоящий filesystem E2E. Test S3
и локальный converter chain проверены отдельно.

Осталось:

- отдельный большой corpus с настоящими JPEG/HEIC/EXIF/corrupt/oversize inputs;
- production media configuration smoke уже относится к Phase 11;
- ручное visual acceptance.

Доказательства: [browser draft](phase5-written-browser-draft.md),
[attachment API](phase5-written-attachment-api.md),
[live storage](phase5-written-storage-live.md),
[reassignment](phase5-written-material-reassignment.md).

### Phase 6 — review/feedback/questions: основной v1 flow готов, compatibility gates открыты

Работают очередь и lease, один combined synonym case, атомарный verdict,
immutable evidence, полноценный annotation editor/viewer, Teacher и Student
reactions, admin reaction inbox, Student/Family projection, no-loss Staff
draft, private text questions и production-build E2E в трёх браузерах.

Осталось по заявленному phase-файлу:

- rehearsed legacy reaction backfill/duplicate report;
- explicit written verdict correction/admin recheck из reaction inbox;
- Telegram composite image для аннотированной проверки;
- таблица решений по idea-only `viewwrittensols*`;
- visual acceptance. Cross-channel Telegram continuation вопросов была
  согласована как желательная, но не блокирующая v1.

Доказательства: [atomic completion](phase6-review-completion.md),
[annotation editor](phase6-review-annotation-editor.md),
[review workspace E2E](phase6-review-workspace.md),
[reaction inbox](phase6-review-reaction-inbox.md),
[support pages/E2E](phase6-support-pages.md).

### Phase 7 — oral/classrooms: функциональное ядро и browser flow готовы

Работают oral windows/result flow, catalog, inherited layout, deterministic
assignment, local draft, history, Excel preview/apply, explicit delivery
preview/batch, Student/Family projection и Telegram retry transport. Устный
путь проходит Chromium/WebKit/Firefox.

Production-build E2E теперь проверяет в трёх браузерах local draft/reload,
confirm, историю, отдельный PWA delivery preview/send, Student notification,
одинаковый Student/Family read model и отсутствие Family notification.
Telegram transport остаётся в отдельном recording/live-test proof и не
подключается к E2E.

Осталось:

- browser-продолжение archive → reassigning → новый confirm/send;
- production-size обезличенный assignment rehearsal и временная граница с
  legacy print;
- visual acceptance полного planner.

Доказательства: [assignments](phase7-classroom-assignments.md),
[delivery](phase7-classroom-delivery.md),
[Telegram transport](phase8-classroom-telegram-transport.md),
[oral E2E](phase7-oral-e2e.md),
[classroom delivery E2E](phase7-classroom-delivery-e2e.md).

### Phase 8 — news/notifications: backend, страницы и browser flow готовы

Работают verified course/group Telegram bindings, live channel adapter,
edits/deletes/albums/media copy, Student/Family feed, offline cache, moderation,
scheduled group banners, notification preferences/events, batching, Web Push
subscription/delivery, quiet sound policy, course overrides и classroom
personal Telegram transport.

Production-build E2E в трёх браузерах проверяет Telegram-origin feed/detail,
Student/Family scope, локальное скрытие баннера, offline read после полного
reload, серверный read acknowledgement и capability-dependent Web Push UI.

Осталось:

- live Web Push проверка на реальном установленном устройстве;
- privacy-safe inventory/reconciliation уже запланированных в Telegram UI
  сообщений перед будущим Staff publisher;
- итоговый delivery-counter/partial-recipient Staff экран и visual acceptance.

Доказательства: `pwa_tests/reports/phase8-*.md`; ключевые —
[live news](phase8-live-news-adapter.md), [feed](phase8-news-feed.md),
[offline](phase8-news-offline.md), [push delivery](phase8-push-delivery.md),
[notification batching](phase8-review-notification-batching.md),
[news/notifications E2E](phase8-news-notifications-e2e.md).

### Phase 9 — Family/progress: функциональное ядро готово, доказательства неполны

Работают multi-child Family context, linked-child authorization, course/group
and mode changes, current lessons, review/photo/annotation reads, Student
course progress, strength chart, activity calendar, achievements и
course-scoped analytics. Student/Family UI и API никогда не показывают
распределение группы, позицию, percentile, rank или маркер ребёнка. Отдельный
production-build browser-сценарий доказывает пересчёт личного прогресса после
более позднего исправления учителя.

Осталось:

- production family-link import dry-run;
- visual acceptance.

Доказательства: [Family E2E](phase9-family-e2e.md),
[progress E2E](phase9-progress-e2e.md),
[analytics](phase9-course-analytics.md),
[1500-student performance](phase9-course-performance.md),
[achievements](phase9-course-achievements.md).

### Phase 10 — Staff data/Google exit: частично готов

Готовы реальные course/group CRUD, independent schedules, Telegram bindings,
Teacher scopes, Student course-enrollment editor, problem workbook
preview/apply/rollback и synonym merge/split impact flow.

Заявленный результат этапа **ещё не достигнут**:

- нет полного Student account CRUD, block/archive и credential reset;
- нет управления Family accounts/links из Staff;
- `/staff/audit` и `/staff/statistics` остаются информационными заглушками;
- Google replacement matrix и production-copy cutover закрывают только problem
  workbook, а не все перечисленные admin workflows;
- нет единого three-browser upload → preview → apply → Student-use сценария;
- visual acceptance отсутствует.

Доказательства готовых срезов: [course catalog](phase10-course-catalog-frontend.md),
[schedules](phase10-course-schedule-frontend.md),
[enrollments](phase10-admin-enrollments-frontend.md),
[staff scopes](phase10-staff-access-frontend.md),
[problem import](phase10-problem-import-apply.md),
[synonyms](phase10-problem-synonym-frontend.md),
[каталог 1500 школьников](phase10-directory-performance.md).

### Phase 11 — hardening/rollout: сильный локальный checkpoint, production gates открыты

Готовы atomic static release/rollback, isolated SQLite restore, migration and
course-enrollment rehearsals, real local converters, permitted test S3 and
Telegram smokes, two workers with NATS/WebSocket, Sentry redaction, IDOR/role
review и текущий полный regression checkpoint.

Осталось:

- server service profile, nginx/FQDN, systemd and real deploy/rollback;
- production/staging Hetzner S3 readiness;
- реальный Sentry event/alert screenshot;
- production backup cron/retention/RPO/RTO evidence;
- physical iOS/Android install/offline/push smoke;
- владельческое visual, product и operational acceptance;
- npm advisory audit требует отдельного явного разрешения, потому что команда
  отправляет имена и версии зависимостей во внешний npm advisory service.

Доказательства: [static release](phase11-static-release.md),
[SQLite restore](phase11-sqlite-restore.md),
[live adapters](phase11-live-adapters-2026-07-30.md),
[two-worker runtime](phase11-two-worker-runtime.md),
[security](phase11-security-checkpoint.md),
[IDOR/roles](phase11-idor-role-review.md),
[production E2E checkpoint](phase11-production-e2e.md).

## Следующая последовательность работ

1. Закрыть недостающий реальный Phase-10 Student/Family account management
   простым вертикальным срезом: короткие SQL-функции, правила в domain-модуле,
   локализованный текст только в HTTP/UI, без новых factories/repositories.
2. Добавить недостающие phase-level browser proofs Phase 7–9; исправление
   существующего Firefox test isolation делать отдельно и минимально.
3. Закрыть media corpus и оставшиеся Phase-6 compatibility reports, не
   переписывая уже работающие submission/review модули.
4. Выполнить production/owner gates после получения Q16, Q17, server/S3/Sentry
   параметров и визуального решения владельца.

До выполнения этих пунктов формулировка «все фазы завершены» была бы неверной.
