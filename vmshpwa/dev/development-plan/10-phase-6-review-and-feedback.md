# Этап 6. Очередь проверки, verdict, аннотации, тред и вопросы

## Результат

Teacher выбирает problem/synonym group, атомарно получает одну работу, видит актуальные фото/контекст, ставит verdict, optional comment, immutable annotation и не более одной internal reaction. Если student дослал материал, complete требует refetch. Student видит заметный verdict в общем Telegram/PWA треде; admin может перепроверить без отдельного dispute workflow.

Дизайн-контракт этапа: [review queue/workspace, verdict controls, feedback thread, annotations/reactions и Storybook stories](18-design-implementation-map.md#phase-6-design).

## Модель данных

Migrations: `0052.pwa_submission_reviews_evidence`,
`0053.pwa_submission_review_annotations` and
`0054.pwa_submission_review_internal_reactions`.

- Эволюция `written_tasks_queue`: rebuild исправляет ошибочную affinity legacy `teacher_id TIMESTAMP` на `INTEGER` FK и добавляет `claim_token`, `claimed_at`, `lease_expires_at`, `lease_version`, `updated_at`; preflight проверяет значения, которые нельзя привести к существующему `users.id`.
- `submission_reviews`, immutable `submission_review_annotations`, current
  `submission_review_internal_reactions` и append-only reaction events с
  one-per-review и часовым окном изменения. Legacy `reactions` не меняется до
  отдельного rehearsed backfill gate.
- Read-only rehearsal legacy reactions строит приватный duplicate/malformed
  report и проверяет возможность точного сопоставления с review round.
  Автоматический backfill или dual-write допустим только для однозначных строк.
  На настоящей базе таких строк нет: legacy `reactions` связаны с `results`, но
  не с конкретной проверкой, поэтому исторические строки остаются отдельной
  Telegram-историей и не получают выдуманную связь.
- `support_threads`, `support_entries` с dual-write/mapping к `questions` и negative problem IDs.
- Review transaction создаёт `results`, review/comment/annotations, фиксирует evidence attachments, снимает queue item и пишет audit/outbox.

## Queue/locking

- Problem group list показывает counts и allowed groups; candidate policy характеризуется нынешним «первые 8 старых, затем выбор» до согласования.
- Claim — conditional update; lease 30 min и heartbeat. Потерянный token не завершает review.
- Locked card показывает teacher и expiry другим staff без приватного draft comment.
- Queue overview группируется по задаче и показывает максимальное время ожидания; list mode по умолчанию идёт от самых старых работ, с фильтрами/сортировками по задаче, группе и ученику.
- После complete/release/abandon пользователь возвращается к problem chooser.
- «Отказ от проверки» — вторичная операция: server lease освобождается, причина не сохраняется. Local draft удаляется только после явного подтверждения; при случайном disconnect тексты/annotation draft восстанавливаются из локального storage.

## Staff review workspace

Desktop: компактная queue/context слева и одна основная хронологическая колонка справа: immutable work viewer/annotation, затем вся существующая student/teacher переписка, затем новый teacher reply и verdict/actions. Mobile сохраняет тот же порядок, queue открывается отдельно. Comment composer не располагается рядом с работой как независимая третья панель.

Fast flow: tap verdict → optional одна реакция из текущего DB registry → save and send. Verdict controls и teacher reaction chips компактны, но точные текстовые подписи всегда видны; emoji-only вариант не используется. Для verdict кроме «Зачтено» сохранение без comment требует confirmation. Реакцию можно изменить/удалить в течение часа; suspicion не меняет verdict.

Comment, текущий verdict choice, reaction choice и сериализуемый annotation state сохраняются в account/review/evidence-version-scoped `localStorage` после каждого осмысленного изменения. Reload восстанавливает их, lost lease/version conflict не очищает, successful complete очищает. Большие временные бинарные derivatives при необходимости используют Dexie, не `localStorage`.

Owner-confirmed annotation core — normalized coordinates + versioned
`pencil|eraser|text|arrow|rectangle` marks и rotation. Optional `highlight` и
palette key допустимы как implementation detail; отдельный tool и точные 4–5
цветов не являются gate. Preview layer never modifies original WebP. Student
видит annotation. Zoom/pan остаются локальным viewer state и не входят в
overlay; renderer сохраняет alignment при любом локальном масштабе холста.

## Thread and visibility

- One chronological thread, latest verdict visually prominent and summarized at top.
- Review completion сверяет thread version. Всё, что стало `submitted` до успешного commit этой проверки, обязано войти в её evidence; изменение thread во время работы даёт `409 THREAD_CHANGED` и требует refetch. Только entry, созданная уже после commit, относится к следующей проверке. Начало claim само по себе не отсекает досланный материал.
- Student: verdict/comment/annotation + own reaction; no internal teacher reaction.
- Teacher: verdict/comment/annotation/internal reactions; no student reaction.
- Admin: all listed elements, complaints/disagreements filters.
- Teacher comment без verdict не поддерживается в task thread. Исправление собственного verdict разрешено; admin recheck заменяет текущий результат по legacy `results` semantics.
- Внутренняя teacher reaction компактна, сохраняет точную подпись и выбирается кликом либо `⌘/Ctrl + Alt + 1…4`; chord работает при фокусе в комментарии и не конфликтует с цифровыми verdict shortcuts.

## Questions/SOS

- Student opens private problem question or general lesson question without magic negative problem IDs. SOS — обычный вопрос человеку, а не отдельный graded flow.
- Вопрос не назначается одному teacher и живёт как общая диалоговая лента teachers + одного student; Telegram adapter остаётся совместимым, cross-channel continuation желательно, но не блокирует v1.
- Privacy/public discussion scope is frozen before UI implementation.

## AI placeholder

Только visual/contracts: «ИИ, не преподаватель», text + optional sanitized SVG, useful/rubbish reaction, copy suggestion. Реальный provider, automatic verdict и production AI call не входят в этап.

## Idea-only reference из другого проекта

`_external_pipelines/viewwrittensols.html`, `viewwrittensols.js` и `_viewmailings_helpers.js` не являются legacy runtime ВМШ и не импортируются в Staff. Их можно использовать только как каталог идей для прототипа:

- выбор нескольких наборов, поиск по ученику/задаче, checked-фильтр, sorting и компактная сводка загруженного;
- deep-link на конкретную работу, переход к следующему фото и предзагрузка соседнего изображения;
- canvas-инструменты select/pan/pen/rectangle/arrow/text, цвета, zoom, rotate/reset, delete, undo/redo, фоновое сохранение и копирование ссылки;
- комментарий к фото, verdict controls, пометка подозрения и исправление ошибочной привязки фото к задаче;
- изолированный preview внешнего mailing HTML и сериализуемые filters как идея для будущего preview, но не как готовый sanitizer.

Все product semantics — chronological thread, synonym provenance, claim/lease, visibility, evidence boundary, immutable original, annotation format, verdict/reaction policy и draft recovery — берутся только из контрактов ВМШ. Принятая идея перереализуется на React/Base UI и покрывается собственными unit/interaction/E2E; внешние endpoints, state shape, score scale, raw colors, DOM и зависимости не копируются.

## Tests

- Multi-worker/process concurrency on shared SQLite + NATS: exactly one claim, lost lease, heartbeat, completion race.
- Transaction fault injection after each write boundary; no half verdict/locked images/queue loss.
- Visibility matrix API + UI; direct URL and WS owner scoping.
- Annotation core pencil/eraser/text/arrow/rectangle/rotation, normalized
  geometry, local-only zoom/pan, sanitization, immutable-after-send and Telegram
  composite PNG; optional highlight/palette проверяются, только если exposed.
- Review draft reload/account isolation/evidence-version conflict/lost lease/success cleanup; unsent question/comment draft не пропадает при route change.
- Legacy queue/discussion/result/reaction and Telegram historical tests.
- Legacy-reaction rehearsal fixtures: written/oral inventory, duplicate and
  malformed-row report, отсутствие PII в aggregate и неизменность исходной БД;
  queue rebuild отдельно проверяет integer FK и не теряет rows.
- Storybook priority: teacher queue + quick review mobile/desktop, long thread, latest verdict, annotations, all reaction visibilities.
- Storybook interaction: internal reaction выбирается/заменяется Mod+Alt chord при фокусе в textarea; повторный chord снимает выбор, `AltGraph` не перехватывается.
- Playwright two staff browser contexts racing; Student context receives refetch and thread; forbidden Teacher admin view.

## Критерии приёмки

- Одна работа не проверяется одновременно двумя teachers.
- Complete атомарен и идемпотентен; asset lock соответствует evidence boundary.
- Visibility enforced by serializer/API, не CSS.
- Latest verdict понятен сразу, история не теряется.
- Admin видит student disagreement и teacher suspicion без отдельных статусов; они не влияют на score автоматически.
- Questions больше не требуют special ID в новом frontend, Telegram не сломан.
- Reload не теряет незавершённый comment/annotation/question; чужой staff account draft не видит.

## Пруфы завершения этапа

- [x] Phase 6A queue rebuild, opaque identity, synonym-case claim,
      heartbeat/release, Staff scope и Telegram-lock compatibility:
      [`phase6-review-queue-leases.md`](../../../pwa_tests/reports/phase6-review-queue-leases.md).
- [x] Phase 6B authenticated HTTP list/claim/heartbeat/release, fail-closed
      public course/group scope, strict TypeScript contracts и account-scoped
      Staff client:
      [`phase6-review-queue-http.md`](../../../pwa_tests/reports/phase6-review-queue-http.md).
- [x] Phase 6C atomic/idempotent completion, exact multi-branch evidence
      snapshot, immutable reviewed entries/assets, target-last legacy result,
      strict HTTP/TypeScript transport и owner-scoped invalidation:
      [`phase6-review-completion.md`](../../../pwa_tests/reports/phase6-review-completion.md).
- [x] Phase 6D versioned normalized annotation manifests for exact evidence,
      all owner-confirmed core tools plus optional highlight, atomic completion,
      immutable SQLite storage и strict HTTP/Zod transport:
      [`phase6-review-annotations.md`](../../../pwa_tests/reports/phase6-review-annotations.md).
- [x] Phase 6E atomic initial internal Teacher reaction, one-hour optimistic
      set/delete/reselect, immutable event history, original-reviewer/scope
      authorization и strict HTTP/Zod transport:
      [`phase6-review-internal-reactions.md`](../../../pwa_tests/reports/phase6-review-internal-reactions.md).
- [x] Read-only legacy reaction rehearsal и manual duplicate/malformed report
      доказали, что точного backfill/dual-write сделать нельзя; legacy rows не
      меняются и остаются доступны Telegram adapter:
      [`phase6-legacy-reaction-rehearsal.md`](../../../pwa_tests/reports/phase6-legacy-reaction-rehearsal.md).
- [x] Межпроцессная claim/completion race, потерянный lease и rollback после
      каждой write boundary:
      [`phase6-review-concurrency-and-faults.md`](../../../pwa_tests/reports/phase6-review-concurrency-and-faults.md).
- [x] Quick review, reload-safe draft, annotation, Student/Family history,
      обе асимметричные reactions, admin inbox и append-only recheck:
      [`phase6-review-workspace.md`](../../../pwa_tests/reports/phase6-review-workspace.md),
      [`phase6-review-annotation-editor.md`](../../../pwa_tests/reports/phase6-review-annotation-editor.md),
      [`phase6-review-reaction-inbox.md`](../../../pwa_tests/reports/phase6-review-reaction-inbox.md),
      [`phase6-review-corrections.md`](../../../pwa_tests/reports/phase6-review-corrections.md).
- [x] Idea-only reference review с таблицей принятых, отложенных и отклонённых
      идей без runtime import:
      [`phase6-external-review-reference.md`](../../../pwa_tests/reports/phase6-external-review-reference.md).
- [x] Visibility matrix защищена serializer/API, owner-scoped realtime и
      production-browser flow; Teacher получает `403` на admin inbox:
      [`phase6-review-audience-fanout.md`](../../../pwa_tests/reports/phase6-review-audience-fanout.md),
      [`phase6-review-reaction-inbox.md`](../../../pwa_tests/reports/phase6-review-reaction-inbox.md).
- [x] Annotation persistence format/version/normalized geometry/rotation tests:
      [`phase6-review-annotations.md`](../../../pwa_tests/reports/phase6-review-annotations.md).
      Interactive editor zoom/pan alignment и Telegram composite renderer
      доказаны отдельными gates. MVP delivery теперь отправляет тихое личное
      Telegram-сообщение и все успешно собранные composite PNG сразу после
      authoritative commit; replay не дублирует отправку, а сбой renderer,
      storage или Telegram не откатывает PWA review:
      [`phase6-review-telegram-delivery-2026-08-03.md`](../../../pwa_tests/reports/phase6-review-telegram-delivery-2026-08-03.md).
- [x] Question draft persistence, account/audience/target isolation and
      page-level clear-after-receipt behavior:
      [`phase6-support-draft-storage.md`](../../../pwa_tests/reports/phase6-support-draft-storage.md),
      [`phase6-support-pages.md`](../../../pwa_tests/reports/phase6-support-pages.md).
      Review comment/verdict/reaction/annotation draft recovery и conflict
      handling доказаны в
      [`phase6-review-workspace.md`](../../../pwa_tests/reports/phase6-review-workspace.md).
- [x] Text-only Student/Staff private-question routes, scoped Staff inbox and
      chronological dialogue composition:
      [`phase6-support-pages.md`](../../../pwa_tests/reports/phase6-support-pages.md).
      Three-browser production E2E covers reload, bidirectional realtime and
      another Student's owner isolation. Attachments, Staff forbidden-scope
      browser proof and Telegram continuation remain open.
- [ ] Storybook priority stories/interactions/a11y автоматизированы (**50 файлов /
      239 PASS**), включая `product-review--workspace`,
      `--feedback-restored-draft`, `--feedback-reaction-shortcuts`,
      `product-review-annotation--editor`,
      `product-feedback--reviewed-written-photo` и reaction inbox. Ручное
      visual acceptance владельцем остаётся открытым; snapshots не менялись.
- [x] Production-build Playwright multi-context в Chromium, WebKit и Firefox:
      **3/3 PASS**; точный охват описан в
      [`phase6-consolidated-gates-2026-08-03.md`](../../../pwa_tests/reports/phase6-consolidated-gates-2026-08-03.md).
- [x] Исторический Telegram regression: `make telegram-history-test` —
      **44 PASS**, без polling и внешних запросов.
- [x] Runbook, recovery и известные границы:
      [`review-workflow.md`](../../docs/review-workflow.md). Сводка текущих
      функциональных и автоматических gates:
      [`phase6-consolidated-gates-2026-08-03.md`](../../../pwa_tests/reports/phase6-consolidated-gates-2026-08-03.md).

## Многокурсовый инкремент Phase 6

Queue объединяет ожидающие submission одного student/synonym-group в один
logical case. Review lock/snapshot перечисляет все submission IDs; teacher
видит provenance всех материалов. Verdict и ответ записываются в problem
последней включённой посылки по `server_received_at`; при равном timestamp
используется стабильный больший internal submission ID только как технический
tie-break. Client time в выборе target не участвует. После split остальные
ветки восстанавливают собственные статусы.

Дополнительный proof: concurrency объединённого case, immutable snapshot, target-last assertion, split status и stories `Product/Review--synonym-combined-case`, `Product/Feedback--synonym-merged-timeline`.
# Дополнение: серийная проверка, 7 сентября 2026

См. [serial-review.md](../../docs/serial-review.md): Staff `review-series-page.tsx`
повторно использует lease и correction, готовит одну следующую работу,
позволяет исправить последнюю оценку без поиска в очереди. Проверки выбора,
пагинации и клавиатуры добавлены рядом с моделями и общим компонентом.

### История и полноценная перепроверка — 9 сентября 2026

См. [review-history.md](../../docs/review-history.md): `/review/history`, поиск
своих/всех проверок, версия исправления с новым immutable evidence/annotations,
явная замена более нового вердикта и optimistic guard. Старые проверки не
редактируются; текущий результат меняется добавлением новой проверки.
Реализация: `review_history.py`, `review_corrections.py`, `review-history-page.tsx`.
Доказательства: 73 backend, 23 frontend и браузерный сценарий в трёх движках.
# Дополнение: контекст задачи в вопросах

Полный номер и название, раскрываемое опубликованное условие в Staff:
[реализация и проверки](../../docs/support-problem-context.md).
