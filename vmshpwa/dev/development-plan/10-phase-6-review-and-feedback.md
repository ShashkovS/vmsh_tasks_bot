# Этап 6. Очередь проверки, verdict, аннотации, тред и вопросы

## Результат

Teacher выбирает problem/synonym group, атомарно получает одну работу, видит актуальные фото/контекст, ставит verdict, optional comment, immutable annotation и не более одной internal reaction. Если student дослал материал, complete требует refetch. Student видит заметный verdict в общем Telegram/PWA треде; admin может перепроверить без отдельного dispute workflow.

## Модель данных

Migration: `pwa_reviews_annotations_queue_leases_reactions_support`.

- Эволюция `written_tasks_queue`: `claim_token`, `claimed_at`, `lease_expires_at`, `lease_version`, `updated_at`.
- `submission_reviews`, immutable `review_annotations`; расширение `reactions` с one-per-review и часовым окном изменения.
- `support_threads`, `support_entries` с dual-write/mapping к `questions` и negative problem IDs.
- Review transaction создаёт `results`, review/comment/annotations, фиксирует evidence attachments, снимает queue item и пишет audit/outbox.

## Queue/locking

- Problem group list показывает counts и allowed groups; candidate policy характеризуется нынешним «первые 8 старых, затем выбор» до согласования.
- Claim — conditional update; lease 30 min и heartbeat. Потерянный token не завершает review.
- Locked card показывает teacher и expiry другим staff без приватного draft comment.
- Queue overview группируется по задаче и показывает максимальное время ожидания; list mode по умолчанию идёт от самых старых работ, с фильтрами/сортировками по задаче, группе и ученику.
- После complete/release/abandon пользователь возвращается к problem chooser.
- «Отказ от проверки» — вторичная операция: server lease освобождается, причина не сохраняется. Local draft удаляется только после явного подтверждения; при случайном disconnect тексты/annotation draft восстанавливаются из локального storage.

## Three-zone Staff

Desktop: queue/context, immutable work viewer, verdict/actions. Mobile: основная зона work+verdict, queue в отдельном drawer.

Fast flow: tap verdict → optional одна реакция из текущего DB registry → save and send. Для verdict кроме «Зачтено» сохранение без comment требует confirmation. Реакцию можно изменить/удалить в течение часа; suspicion не меняет verdict.

Annotation format — normalized coordinates + versioned strokes/marks; preview layer never modifies original WebP. Student видит annotation, zoom сохраняет alignment.

## Thread and visibility

- One chronological thread, latest verdict visually prominent and summarized at top.
- Review completion сверяет thread version. Всё submitted до commit включается в evidence; более поздний entry относится к следующей проверке.
- Student: verdict/comment/annotation + own reaction; no internal teacher reaction.
- Teacher: verdict/comment/annotation/internal reactions; no student reaction.
- Admin: all listed elements, complaints/disagreements filters.
- Teacher comment без verdict не поддерживается в task thread. Исправление собственного verdict разрешено; admin recheck заменяет текущий результат по legacy `results` semantics.

## Questions/SOS

- Student opens private problem question or general lesson question without magic negative problem IDs. SOS — обычный вопрос человеку, а не отдельный graded flow.
- Вопрос не назначается одному teacher и живёт как общая диалоговая лента teachers + одного student; Telegram adapter остаётся совместимым, cross-channel continuation желательно, но не блокирует v1.
- Privacy/public discussion scope is frozen before UI implementation.

## AI placeholder

Только visual/contracts: «ИИ, не преподаватель», text + optional sanitized SVG, useful/rubbish reaction, copy suggestion. Реальный provider, automatic verdict и production AI call не входят в этап.

## Tests

- Multi-worker/process concurrency on shared SQLite + NATS: exactly one claim, lost lease, heartbeat, completion race.
- Transaction fault injection after each write boundary; no half verdict/locked images/queue loss.
- Visibility matrix API + UI; direct URL and WS owner scoping.
- Annotation pencil/eraser/rotation/4–5 colors, geometry/zoom/sanitization, immutable-after-send and Telegram composite PNG.
- Legacy queue/discussion/result/reaction and Telegram historical tests.
- Storybook priority: teacher queue + quick review mobile/desktop, long thread, latest verdict, annotations, all reaction visibilities.
- Playwright two staff browser contexts racing; Student context receives refetch and thread; forbidden Teacher admin view.

## Критерии приёмки

- Одна работа не проверяется одновременно двумя teachers.
- Complete атомарен и идемпотентен; asset lock соответствует evidence boundary.
- Visibility enforced by serializer/API, не CSS.
- Latest verdict понятен сразу, история не теряется.
- Admin видит student disagreement и teacher suspicion без отдельных статусов; они не влияют на score автоматически.
- Questions больше не требуют special ID в новом frontend, Telegram не сломан.

## Пруфы завершения этапа

- [ ] Revision/migration/dual-write/backfill: `<sha/paths/results>`.
- [ ] Queue concurrency/lease/fault-injection report: `<path/result>`.
- [ ] Demo quick review + annotation + Student thread + admin reactions: `<routes/evidence>`.
- [ ] Visibility matrix API/E2E: `<path/result>`.
- [ ] Annotation format/version/zoom tests: `<result>`.
- [ ] Storybook priority stories/interactions/a11y/visual approval: `<ids/paths>`.
- [ ] Playwright multi-context 3 browsers: `<result>`.
- [ ] Telegram queue/discussion/results/questions historical tests: `<result>`.
- [ ] Docs/review runbook/known limitations/acceptance: `<paths/issues/name/date>`.
