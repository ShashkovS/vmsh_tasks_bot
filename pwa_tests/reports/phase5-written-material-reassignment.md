# Phase 5 — append-only перенос письменных материалов

Дата проверки: 2026-07-28. Revision: `0e8b84f`.

## Проверяемый результат

- Staff preview и commit используют отдельные strict JSON endpoints:
  `POST /staff/api/v1/submission-material-reassignments/preview` и
  `POST /staff/api/v1/submission-material-reassignments`.
- Операция переносит логическую проекцию выбранного текста и/или фотографий в
  другую конкретную задачу того же школьника. Исходные `problem_id`, entry,
  attachment, object key, bytes, result и verdict не переписываются и не
  удаляются.
- Заголовок операции сохраняется в `submission_material_reassignments`, а
  выбранные элементы — отдельными строками в
  `submission_material_reassignment_items`. Один idempotency key соответствует
  одному payload; точный повтор возвращает прежний receipt, несовпадающий
  payload отклоняется.
- Preview и commit проверяют существование обеих задач, исторический доступ
  школьника к целевой группе, текущие source/target thread versions и Staff
  scope сразу для источника и назначения. Teacher без актуального scope получает
  `403`, а stale optimistic version — `409` без частичной записи.
- Student projection скрывает выбранный материал в исходной истории и показывает
  его в целевой с provenance `staff_reassignment`: IDs операции, исходные и
  целевые thread/problem и серверное время. Частичный перенос текста и отдельных
  фотографий поддерживается.
- Перенос разрешён после review lock: immutable evidence и verdict остаются в
  исходной проверке, а целевая задача получает только новую логическую проекцию.
  Типы задач и способы сдачи намеренно не сравниваются.
- После commit Student получает owner-scoped invalidation для исходной и целевой
  задачи. Idempotent replay повторных invalidations не создаёт.

## Реализующие файлы

- Repository, projection и atomic commit:
  [`written_submissions.py`](../../db_methods/pwa/written_submissions.py).
- Staff HTTP boundary, permissions и invalidations:
  [`written_submission_routes.py`](../../apps/pwa_api/written_submission_routes.py).
- TypeScript/Zod wire contract:
  [`written-submissions.ts`](../../vmshpwa/packages/contracts/src/written-submissions.ts).
- Repository integration:
  [`test_submission_repository.py`](../integration/test_submission_repository.py).
- Real aiohttp/SQLite integration:
  [`test_content_http_api.py`](../integration/test_content_http_api.py).
- Contract and Student projection fixtures:
  [`written-submissions.test.ts`](../../vmshpwa/packages/contracts/src/written-submissions.test.ts).

## Автоматические доказательства

- Focused TypeScript contracts: **1 файл / 8 PASS**.
- Focused repository reassignment: **3 PASS**.
- Focused real aiohttp reassignment: **1 PASS**.
- Broad written repository/HTTP regression: **27 PASS**.
- Полный `make pwa-test`: **47 frontend-файлов / 363 PASS** и **1227 Python
  PASS / 3 intentional skips / 1 existing SymPy warning**.
- `make pwa-lint`, `make pwa-typecheck` и `make pwa-build`: **PASS**. Student и
  Family собрали `injectManifest` service workers; Staff собрал обычный SPA.
- Проверены: text+photo batch, частичная проекция, exact replay, idempotency
  mismatch, stale conflict без проекции, post-review locked evidence/verdict,
  anonymous `401`, teacher scope removal `403` и ровно две owner invalidations.
- Автоматические тесты используют временные SQLite и локальный in-process
  broker. Telegram, Google, S3, production credentials и `db/vmsh.db` не
  использовались.

## Открытые границы

- Staff UI выбора материалов, поиска целевой задачи, preview и подтверждения ещё
  не подключён; visual/interaction gate поэтому остаётся открытым.
- Для filesystem storage Staff пока не имеет отдельного authenticated media URL:
  preview содержит Student media path, который нельзя считать готовой Staff
  загрузкой. Это должно быть закрыто до UI vertical.
- Один физический элемент нельзя повторно перенести новой операцией. Если продукту
  понадобится цепочка исправлений, потребуется явно определённая latest-projection
  семантика, а не молчаливое переписывание прежней операции.
- Другие преподаватели пока не получают отдельную Staff queue invalidation;
  acting Staff видит authoritative commit response, Student — две owner-scoped
  invalidations. Общая очередь относится к Phase 6.
- Storybook и visual snapshots не менялись.
