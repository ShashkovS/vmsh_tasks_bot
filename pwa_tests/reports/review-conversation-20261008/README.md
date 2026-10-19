# Полная переписка старых проверок — 8 октября 2026

Реализована общая карточка Teacher/Admin с полной сохранённой PWA/Telegram
перепиской, поздними ответами, вердиктами и защищёнными вложениями. Состав
immutable evidence, исправление вердикта, черновик и optimistic guards сохранены.
Требования и интерфейсы: [review-history.md](../../../vmshpwa/docs/review-history.md#полная-переписка--8-октября-2026).

## Доказательства

- Runtime-контракт и клиент: [review-history.ts](../../../vmshpwa/packages/contracts/src/review-history.ts),
  [review-queue-client.ts](../../../vmshpwa/packages/app-shell/src/review-queue-client.ts).
- Backend: [проекция](../../../models/pwa/review_conversation.py),
  [чтение SQLite](../../../db_methods/pwa/review_conversation.py),
  [HTTP](../../../apps/pwa_api/review_routes.py). Базовая авторизация выбранной
  проверки включает все evidence-группы; последующие проверки и переносы
  проверяются по текущему scope. Внутренние реакции/аудит исключены.
- UI: [ReviewConversation](../../../vmshpwa/apps/staff/src/review-conversation.tsx),
  [общая карточка](../../../vmshpwa/apps/staff/src/review-history-page.tsx),
  [HistoryEvents](../../../vmshpwa/apps/staff/src/student-results-history.tsx).
  Read-only серия привязывает переписку к исходному разрешённому review ID.
- HTTP-регрессии: [test_review_conversation.py](../../integration/test_review_conversation.py),
  [test_review_queue_http_api.py](../../integration/test_review_queue_http_api.py),
  [test_student_results.py](../../integration/test_student_results.py): **30 уникальных PASS**.
  Совместный focused запуск дал 29 PASS и обнаружил отсутствие attachment service
  в новом media fixture; после исправления wiring единственный тест повторён: 1 PASS.
  Проверены 58 событий/две страницы, поздние ответы обоих evidence-уровней,
  `.txt`, фото, отсутствующие/выходящие за корень файлы, dedup, скрытый draft,
  неизменность snapshot, чужие ID, отзыв peer scope и Admin-доступ.
- Frontend: **1053 PASS**, включая порядок реплик, retry первой/следующей страницы,
  сохранность загруженных событий при ошибке, контракт media URLs и transport.
  Выполнен frontend этап `make pwa-test`; начатый им повтор Python остановлен
  до выполнения тестов, поскольку полный Python уже был запущен в fast gate.
- Storybook: **363 уникальных PASS**. Первый запуск `make pwa-storybook-test`:
  362 PASS, golden-corpus module не загрузился из-за отсутствовавших PDF.
  Скопирован только `_vmsh_examples` из основного checkout; повторён только
  `packages/content/src/golden-corpus.stories.tsx`: 1 PASS.
- Chromium E2E: **6 PASS**, четыре production bundles собраны. Выполнен штатный
  lock-aware runner с `--browser chromium --mode review --mode student-results`.
  [Receipt](e2e.json). [Новый сценарий](../../../vmshpwa/e2e/student-results.spec.ts)
  проверяет Teacher/Admin, reload черновика, поздние Telegram-сообщения, пагинацию
  и равенство материалов исходной/исправленной проверки. Существующие сценарии
  review подтверждают Student/Family projections, аннотации и append-only correction.
- Светлая/тёмная темы при 1280×900 осмотрены: обе стороны диалога читаемы,
  длинная история прокручивается. [Light](old-review-light.png), [dark](old-review-dark.png).
- Format, TypeScript, ESLint, CSS lint, frontend/backend i18n и focused Ruff PASS.
  Выполнен `make pwa-i18n-extract`; английские переводы заполнены.

## Полный gate и оставшиеся ограничения

`make pwa-check-fast PWA_E2E_MODES="review student-results"` был запущен.
Последний общий receipt: `.runtime/vmshpwa/checks/20261008T065007.207879Z/summary.json`.
Статические этапы PASS; Python: 2823 PASS / 8 SKIP / 18 FAIL, включая один
исправленный новый fixture. Оставшиеся **17 незатронутых failures**:
14 зависят от отсутствовавших `_vmsh_examples` / `_external_pipelines`, два
требуют отсутствующий prod profile, один `test_phase10_staff_access` расходится
из-за фиксированного auth clock и текущего UTC при записи прав. Связанные
с исправлением HTTP-тесты затем прошли; оставшиеся frontend/Storybook/E2E
этапы выполнены отдельно. Полный gate **не заявляется зелёным**. Production
credentials и production/human state не использовались. Пустой локальный
ignored test profile и эталонные PDF оставлены для тестового окружения.

Миграций, commit/push и production deployment нет. WebKit/Firefox остаются
полным release gate; для этого небольшого исправления выбран Chromium.
