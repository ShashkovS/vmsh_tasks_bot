# Phase 5 — append-only перенос письменных материалов

Дата проверки: 2026-07-28. Revisions: repository/API `0e8b84f`, Staff media
authorization `08ac0bf`, typed Staff client `89d0427`, product/Storybook
prototype `a2187c7`.

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
- Staff preview использует отдельные authenticated media URLs. Доступ к WebP
  повторно проверяет Staff permission и актуальный course/group scope по точной
  revision задачи; Student cookie на Staff route не принимается.
- Typed Staff client выполняет preview, commit и защищённую загрузку media,
  проверяет Zod-контракты, сохраняет byte-identical body/idempotency key при
  единственном retry после `401` и не включает prototype/MSW-путь.
- Storybook-прототип покрывает выбор отдельных сообщений и фотографий, целевую
  задачу, необязательную причину для audit, preview/confirm и предупреждение о
  неизменяемых evidence/verdict после начала проверки.

## Реализующие файлы

- Repository, projection и atomic commit:
  [`written_submissions.py`](../../db_methods/pwa/written_submissions.py).
- Staff HTTP boundary, permissions и invalidations:
  [`written_submission_routes.py`](../../apps/pwa_api/written_submission_routes.py).
- TypeScript/Zod wire contract:
  [`written-submissions.ts`](../../vmshpwa/packages/contracts/src/written-submissions.ts).
- Typed Staff transport:
  [`written-material-reassignment-client.ts`](../../vmshpwa/packages/app-shell/src/written-material-reassignment-client.ts).
- Product component и interaction stories:
  [`written-material-reassignment.tsx`](../../vmshpwa/packages/product/src/written-material-reassignment.tsx)
  и
  [`written-material-reassignment.stories.tsx`](../../vmshpwa/packages/product/src/written-material-reassignment.stories.tsx).
- Repository integration:
  [`test_submission_repository.py`](../integration/test_submission_repository.py).
- Real aiohttp/SQLite integration:
  [`test_content_http_api.py`](../integration/test_content_http_api.py).
- Contract and Student projection fixtures:
  [`written-submissions.test.ts`](../../vmshpwa/packages/contracts/src/written-submissions.test.ts).

## Автоматические доказательства

- Focused TypeScript contracts и Staff client: **2 файла / 12 PASS**.
- Focused repository reassignment: **3 PASS**.
- Focused real aiohttp reassignment: **1 PASS**.
- Broad written repository/HTTP regression: **27 PASS**.
- Focused Storybook browser-mode: **1 файл / 2 PASS**, включая addon-a11y в
  режиме `error`.
- Полный `make pwa-storybook-test`: **39 файлов / 190 PASS**.
- Полный `make pwa-test`: **48 frontend-файлов / 367 PASS** и **1227 Python
  PASS / 3 intentional skips / 1 existing SymPy warning**.
- `make pwa-lint`, `make pwa-typecheck` и `make pwa-build`: **PASS**. Student и
  Family собрали `injectManifest` service workers; Staff собрал обычный SPA.
- Проверены: text+photo batch, частичная проекция, exact replay, idempotency
  mismatch, stale conflict без проекции, post-review locked evidence/verdict,
  anonymous `401`, teacher scope removal `403` и ровно две owner invalidations.
- Автоматические тесты используют временные SQLite и локальный in-process
  broker. Telegram, Google, S3, production credentials и `db/vmsh.db` не
  использовались.
- Ручной визуальный осмотр выполнен в agent Storybook на desktop и mobile-light.
  Найденный mobile overflow целевого select исправлен до фиксации; snapshots не
  обновлялись. Story IDs: `product-review--material-reassignment` и
  `product-review--material-reassignment-post-review`.

## Открытые границы

- Reusable Staff UI, transport и visual/interaction gate готовы, но production
  review route ещё не соединяет их с реальной очередью, thread detail и поиском
  целевой задачи. Это относится к Phase 6 vertical.
- Один физический элемент нельзя повторно перенести новой операцией. Если продукту
  понадобится цепочка исправлений, потребуется явно определённая latest-projection
  семантика, а не молчаливое переписывание прежней операции.
- Другие преподаватели пока не получают отдельную Staff queue invalidation;
  acting Staff видит authoritative commit response, Student — две owner-scoped
  invalidations. Общая очередь относится к Phase 6.
- Visual snapshots намеренно не обновлялись до отдельного approval владельцем.
