# Аудит выполнения плана разработки — 3 августа 2026 года

Этот отчёт повторно сверяет этапы 0–11 с фактически закоммиченными миграциями,
маршрутами, интерфейсами, тестами и proof-файлами. Он заменяет выводы
[`development-plan-completion-audit-2026-07-30.md`](development-plan-completion-audit-2026-07-30.md),
которые устарели после последующих инкрементов, но не удаляет прежний отчёт из
истории.

Проверенная функциональная ревизия: `40f30ac`.

Незакоммиченные параллельные изменения Family notification UI, дизайн-системы
и планов в этот аудит не включены. Наличие файла, Storybook-прототипа или старой
галочки само по себе не считается доказательством завершения.

## Текущий автоматический checkpoint

`make python-test` на этой ревизии, по восемь изолированных xdist workers в
каждом последовательном наборе:

- legacy: **124 passed, 1 skipped**, 11,68 с;
- PWA: **1586 passed, 6 skipped**, 61,77 с;
- итого: **1710 passed, 7 skipped**, около 74 секунд pytest time.

Live NATS, S3 и Telegram smokes являются отдельными opt-in gates и в этот
обычный hermetic regression не входят. Последний широкий frontend unit запуск
в текущем worktree: **114 файлов / 594 tests**, strict TypeScript PASS. Он не
выдаётся за clean-revision checkpoint, потому что запуск видел соседний
незакоммиченный Family UI. Общий ESLint грязного worktree также не используется
как доказательство: он останавливается на незакоммиченном соседнем
`family-notifications-page.tsx`.

## Значения статусов

- **Программный gate закрыт** — заявленный v1 путь реализован и имеет прямые
  unit/integration/browser или live-adapter доказательства.
- **Частично закрыт** — существенная часть работает, но в результате этапа
  отсутствует ещё один продуктовый путь, а не только ручное принятие.
- **Внешний gate** — нужен production runtime, реальное устройство, решение
  владельца или ручное визуальное/операционное принятие.
- **Отложенная совместимость** — текущий новый путь работает, но исторические
  данные невозможно переносить без отдельного решения; фиктивный backfill не
  создаётся.

Ни одна фаза не называется полностью завершённой, пока у неё открыт хотя бы
один обязательный gate из собственного phase-файла.

## Phase 0 — baseline и совместимость

**Состояние: программная baseline закрыта; внешние acceptance и service-host
gates открыты.**

Доказано:

- human/agent runtime разделены по портам, SQLite, media root, NATS prefix и
  browser storage;
- app factory запускает PWA API без Telegram polling и Google loader;
- deterministic seed, schema inventory, golden/characterization fixtures,
  filesystem storage и converter probes работают;
- разрешённые test-S3/test-Telegram и local NATS smokes выполнены отдельно;
- реальные event logs профилированы;
- двухпроцессный SQLite/NATS сценарий проверил login burst и representative
  server-side outbox flush: 16 письменных сдач, 32 фотографии по 512 KiB,
  16 MiB file IO, полные metadata/idempotency/queue writes, ноль исчерпанных
  `SQLITE_BUSY` и half-write. Допустимый user-visible busy budget для такого
  клубного burst зафиксирован как ноль, без выдуманного production SLA.

Прямые доказательства: [`baseline-v1.md`](baseline-v1.md),
[`runtime-isolation-phase0.md`](runtime-isolation-phase0.md),
[`phase0-live-integration-2026-07-27.md`](phase0-live-integration-2026-07-27.md),
[`phase11-two-worker-runtime.md`](phase11-two-worker-runtime.md).

Открыто:

- owner visual/phase acceptance;
- production service-host повтор converter capability gate.

## Phase 1 — authentication и access control

**Состояние: программный v1 gate закрыт; production activation открыт.**

Доказаны audience-scoped cookie sessions, refresh/revoke/device list,
Student/Family/Staff login, Family-child authorization, Staff scopes,
authenticated WebSocket, CSRF/origin checks и trusted-proxy boundary. Последний
зафиксированный browser auth matrix: 60/60 в Chromium, WebKit и Firefox.

Прямые доказательства: [`auth-preflight.md`](auth-preflight.md),
[`phase1-auth-import-tooling.md`](phase1-auth-import-tooling.md),
[`phase1-auth-race-hardening.md`](phase1-auth-race-hardening.md) и
[`05-phase-1-auth.md`](../../vmshpwa/dev/development-plan/05-phase-1-auth.md).

Открыто:

- owner-only решения по legacy blockers/collisions и controlled production
  import/apply;
- nginx/FQDN smoke на целевом сервере;
- ручное принятие login/session/forbidden states.

## Phase 2 — LaTeX, assets и публикация

**Состояние: программный v1 gate закрыт; production-history и visual gates
открыты.**

Работают versioned TeX compiler, client KaTeX projection, Telegram Rich HTML,
PDF derivative, TikZ→SVG, raster/HEIC→WebP, content-addressed assets, bulk
upload, matching/metadata review, независимые condition/hint/solution
schedules, publication и rollback. Production-build E2E прошёл один полный
путь в каждом из трёх браузеров.

Прямые доказательства: [`phase2-content-compiler.md`](phase2-content-compiler.md),
[`phase2-real-content-corpus.md`](phase2-real-content-corpus.md),
[`phase2-content-assets-live.md`](phase2-content-assets-live.md),
[`phase2-content-e2e.md`](phase2-content-e2e.md),
[`phase2-content-history-backfill.md`](phase2-content-history-backfill.md).

Открыто:

- owner-reviewed mapping/rehearsal/apply истории 1–38 на отдельной production
  копии;
- подтверждение intentional differences со всеми внешними pipeline outputs;
- owner visual acceptance реальных длинных условий и Staff diagnostics.

## Phase 3 — Student reading и offline

**Состояние: программный v1 gate закрыт; owner visual gate открыт.**

Доказаны course/group access, «Сейчас», архив занятий, длинный и focused task,
audited reveal подсказки, KaTeX/SVG, owner-isolated IndexedDB cache, quota и
cold-offline reading. Backend при reconnect остаётся источником истины.

Прямые доказательства: [`phase3-course-access-api.md`](phase3-course-access-api.md),
[`phase3-student-home.md`](phase3-student-home.md),
[`phase3-student-problem-list.md`](phase3-student-problem-list.md),
[`phase3-student-offline-reading.md`](phase3-student-offline-reading.md),
[`phase3-long-math-rendering.md`](phase3-long-math-rendering.md).

Открыто только окончательное визуальное принятие Student reading matrix.

## Phase 4 — тестовые задачи

**Состояние: программный v1 gate закрыт; owner visual gate открыт.**

Доказаны все 23 legacy answer types, contextual validation, visible-label
`SELECT_ONE`, trusted-admin checker compatibility, attempt limits, immediate
verdict, idempotency, deadline/client-time audit, reload-safe draft, Dexie
outbox/retry и Staff recheck после исправления конфигурации. Telegram adapter
использует ту же domain policy. Production E2E прошёл в трёх браузерах.

Прямое сводное доказательство:
[`phase4-test-submission-domain-and-repository.md`](phase4-test-submission-domain-and-repository.md).

Открыто только owner visual acceptance. Structured PWA ledger для старых
Telegram attempts не является v1 gate: legacy persistence остаётся рабочим
параллельным adapter.

## Phase 5 — письменные сдачи

**Состояние: программный v1 gate закрыт; исторический backfill и owner visual
gate открыты.**

Доказаны 1–10 фотографий, client WebP worker, server fallback для JPEG/HEIC,
EXIF removal, previews/reorder, reload-safe offline outbox, atomic replacement,
immutable reviewed evidence, filesystem/S3 behavior и настоящий browser flow.
Отдельный corpus теперь покрывает orientation/GPS, corrupt и oversize inputs.

Прямые доказательства:
[`phase5-written-consolidated-gates.md`](phase5-written-consolidated-gates.md),
[`phase5-written-media-corpus.md`](phase5-written-media-corpus.md),
[`phase5-written-storage-live.md`](phase5-written-storage-live.md).

Открыто:

- ответ на вопрос 2 в
  [`22-development-questions.md`](../../vmshpwa/dev/development-plan/22-development-questions.md):
  40 531 Telegram-only historical rows не содержат payload, поэтому безопасный
  backfill сейчас невозможен;
- owner visual acceptance submission states.

## Phase 6 — review, feedback и вопросы

**Состояние: основной review v1 закрыт; support media/Telegram continuation и
owner visual gate открыты.**

Доказаны queue lease, один combined synonym case, atomic verdict, immutable
evidence snapshot, photo annotation, Teacher/Student reactions, admin inbox,
append-only correction/recheck, Student/Family projection, owner-scoped
realtime, reload-safe Staff draft и text-only private questions. Production
review flow прошёл в трёх браузерах; historical Telegram regression — 44 PASS.

Прямое доказательство:
[`phase6-consolidated-gates-2026-08-03.md`](phase6-consolidated-gates-2026-08-03.md).

Открыто:

- вложения к support thread и продолжение одной переписки через Telegram;
- wiring уже проверенного annotation PNG в реальную Telegram delivery;
- owner visual acceptance review/support surfaces.

Эти пробелы нельзя честно закрыть добавлением второго write path рядом с
существующим большим support repository. До отдельного согласованного
упрощения persistence новый слой abstractions не добавляется.

## Phase 7 — oral и аудитории

**Состояние: программный v1 gate закрыт; operational/visual gates открыты.**

Доказаны oral windows, no-store join secret, Staff oral result, classroom
catalog, multi-course event, inherited layout, deterministic assignments,
fuzzy search, nullable demographics, reload-safe batch draft, history,
one-time Excel preview/apply, explicit PWA/Telegram delivery snapshot,
Student/Family projection и retry transport. Scale rehearsal: 1500 очных
Student / 15 аудиторий, recalculation+confirm 0,55 с.

Прямое доказательство:
[`phase7-consolidated-gates-2026-08-03.md`](phase7-consolidated-gates-2026-08-03.md).

Открыто:

- owner-run rehearsal «ранняя рассылка → поздние смены режима → новая
  подтверждённая версия → финальная печать»;
- реальный preview текущего classroom workbook перед one-time import;
- owner visual acceptance;
- печать остаётся явно вне v1 и не подменяется новым фиктивным export API.

Последний повтор browser matrix 3 августа не дошёл до приложения из-за
macOS `MachPortRendezvous`/`SIGABRT`; он не отменяет предыдущие 9/9 PASS, но и
не считается свежим подтверждением.

## Phase 8 — news, realtime и notifications

**Состояние: основной news/notification v1 почти закрыт; Family digest,
physical push и owner visual gates открыты.**

Доказаны Telegram channel ingest/edit/albums/media copy, explicit deletion
reconciliation, Student/Family feed и offline cache, moderation, verified
course/group bindings, scheduled local PWA news, edit/reschedule до публикации,
due-time foreground invalidation, group banners, notification core,
course-scoped preferences, batching, Web Push subscription/delivery, quiet
sound policy и delivery observability. Запланированные вручную Telegram posts
имеют отдельный offline cutover inventory.

Ключевые доказательства:

- [`phase8-live-news-adapter.md`](phase8-live-news-adapter.md);
- [`phase8-news-feed.md`](phase8-news-feed.md);
- [`phase8-news-offline.md`](phase8-news-offline.md);
- [`phase8-push-delivery.md`](phase8-push-delivery.md);
- [`phase8-news-notifications-e2e.md`](phase8-news-notifications-e2e.md);
- [`phase8-local-scheduled-news.md`](phase8-local-scheduled-news.md);
- [`phase8-local-news-editing-2026-08-03.md`](phase8-local-news-editing-2026-08-03.md);
- [`phase8-news-source-deletion-reconciliation.md`](phase8-news-source-deletion-reconciliation.md);
- [`phase8-telegram-scheduled-queue-reconciliation.md`](phase8-telegram-scheduled-queue-reconciliation.md).

Открыто:

- weekly Family digest semantics — вопрос 8 в
  [`22-development-questions.md`](../../vmshpwa/dev/development-plan/22-development-questions.md);
- редактирование уже опубликованной локальной новости — вопрос 7;
- live Web Push на установленном iOS/Android устройстве;
- owner execution реального Telegram scheduled-queue inventory;
- owner visual acceptance delivery/moderation/settings states;
- свежий browser rerun после устранения локального macOS launcher failure.

## Phase 9 — Family и личный прогресс

**Состояние: основной read/progress v1 закрыт; provisioning, streak,
distribution policy и visual gates открыты.**

Доказаны multi-child context, Family authorization, course/group/mode changes,
current lessons, review/photo/annotation read, course-separated personal
progress, strength, activity calendar, initial achievements и course analytics.
Student/Family projection не содержит rank, percentile, позиции или маркера
ребёнка на групповом графике. Family-link CSV имеет безопасный read-only
preview с синтетическим migrated-SQLite proof.

Прямые доказательства: [`phase9-family-e2e.md`](phase9-family-e2e.md),
[`phase9-progress-e2e.md`](phase9-progress-e2e.md),
[`phase9-course-analytics.md`](phase9-course-analytics.md),
[`phase9-course-performance.md`](phase9-course-performance.md),
[`phase9-course-achievements.md`](phase9-course-achievements.md),
[`phase9-family-link-import-preview-2026-08-03.md`](phase9-family-link-import-preview-2026-08-03.md).

Открыто:

- Family batch provisioning/apply и передача первого credential — вопрос 1;
- точные streak rules — вопрос 5;
- полное удаление либо разрешение анонимной distribution — вопрос 6;
- owner production Family-link preview/apply;
- owner visual acceptance Family/progress pages.

## Phase 10 — Staff data и отказ от Google

**Состояние: Staff software core почти закрыт; полный Google cutover не
достигнут.**

Доказаны course/group CRUD, independent schedules, Telegram bindings, Teacher
scopes, enrollment editor, Student account lifecycle, Family account/link
management, searchable audit, statistics/dashboard, task-workbook
preview/apply/rollback, synonym merge/split и reload-safe metadata drafts.
Полный loader inventory теперь фиксирует все шесть Google sheets и
неатомарность `/update_all`.

Ключевые доказательства:
[`phase10-problem-workbook-replacement.md`](phase10-problem-workbook-replacement.md),
[`phase10-course-catalog-frontend.md`](phase10-course-catalog-frontend.md),
[`phase10-course-schedule-frontend.md`](phase10-course-schedule-frontend.md),
[`phase10-account-lifecycle-2026-07-30.md`](phase10-account-lifecycle-2026-07-30.md),
[`phase10-family-account-ui.md`](phase10-family-account-ui.md),
[`phase10-staff-audit.md`](phase10-staff-audit.md),
[`phase10-staff-statistics.md`](phase10-staff-statistics.md),
[`phase10-google-loader-inventory-2026-08-03.md`](phase10-google-loader-inventory-2026-08-03.md),
[`phase10-google-bulk-cutover-guard-2026-08-03.md`](phase10-google-bulk-cutover-guard-2026-08-03.md),
[`phase10-metadata-grid-drafts-2026-08-03.md`](phase10-metadata-grid-drafts-2026-08-03.md).

Открыто:

- initial Student/Family provisioning зависит от course/group mapping и
  credential-delivery decisions;
- `_BotUIMsgs` и `_BotSettings` — вопросы 3–4;
- owner-run полный недельный Staff workflow и объявленная дата cutover;
- остальные external processes не считаются выключенными только потому, что
  заменён лист «Задачи»;
- owner visual acceptance dense Staff states.

## Phase 11 — hardening и rollout

**Состояние: сильный локальный release checkpoint; production rollout открыт.**

Доказаны atomic static release/rollback, isolated SQLite restore, migration и
course-enrollment rehearsals, converter chain, test S3/Telegram, NATS с двумя
workers, WebSocket resync, dependency audit, Sentry redaction, IDOR/role review,
security headers и read-only media growth/orphan inventory. Inventory не имеет
delete API и не превращает diagnostic в автоматическую retention policy.

Ключевые доказательства:
[`phase11-static-release.md`](phase11-static-release.md),
[`phase11-sqlite-restore.md`](phase11-sqlite-restore.md),
[`phase11-live-adapters-2026-07-30.md`](phase11-live-adapters-2026-07-30.md),
[`phase11-two-worker-runtime.md`](phase11-two-worker-runtime.md),
[`phase11-security-checkpoint.md`](phase11-security-checkpoint.md),
[`phase11-sentry-privacy.md`](phase11-sentry-privacy.md),
[`phase11-dependency-audit-2026-08-02.md`](phase11-dependency-audit-2026-08-02.md),
[`phase11-service-worker-cache-boundary-2026-08-03.md`](phase11-service-worker-cache-boundary-2026-08-03.md),
[`phase11-media-inventory-2026-08-03.md`](phase11-media-inventory-2026-08-03.md).

Открыто:

- production service profile, nginx/FQDN, systemd и реальный deploy/rollback;
- production Hetzner S3 readiness и production media inventory;
- реальный Sentry event/alert;
- production backup schedule, retention, measured RPO/RTO;
- physical iOS/Android install/offline/push smoke;
- all-groups reconciliation/rollback rehearsal;
- product, visual и operational acceptance владельцем.

## Противоречия и устаревшие отметки в phase-файлах

Чеклисты Phase 0, 1, 4, 8 и 11 содержат старые `<path/result>` placeholders,
хотя часть соответствующих proof уже существует. Автоматически проставлять им
галочки нельзя: один пункт часто смешивает программное доказательство и ещё не
пройденный owner/production gate. Этот аудит является временной точной картой;
при следующем изменении сам phase-пункт нужно разделять на две отдельные строки,
а не объявлять смешанный пункт закрытым.

Также нельзя использовать как доказательство:

- Storybook story без interaction/a11y run и owner visual approval;
- старый успешный browser run как свежий run после изменения затронутого кода;
- test S3 вместо readiness production Hetzner bucket;
- NATS event как durable log вместо повторного authoritative SQLite GET;
- отсутствие очереди review как автоматический сигнал «проверка занятия
  завершена» до ответа на вопрос 8.

## Следующий порядок независимой разработки

1. После завершения соседнего Family notification UI вернуть зелёные
   frontend lint/type/unit/storybook/build gates и закоммитить его отдельно.
2. После завершения соседнего `oral_window` notification slice сверить его
   общий scheduler/allowlist и отдельно определить `deadline` semantics, не
   угадывая Family digest rules.
3. Подготовить исполняемые production runbooks/checklists Phase 11, оставляя
   реальные server/device результаты незакрытыми до их фактического запуска.
4. После ответов владельца закрыть вопросы 1–8 отдельными вертикальными
   срезами, а не общим speculative subsystem.

До закрытия перечисленных gates формулировка «все этапы разработки завершены»
остаётся недоказанной.
