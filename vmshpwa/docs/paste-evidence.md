# Доля вставленного текста

Решение владельца, 11 октября 2026: приблизительно оценивать вставленные
символы, оставшиеся в каждом письменном сообщении. Staff показывает
«Вставлено ≈ …%»: 0 скрыт, 1–24 neutral, 25–74 warning, 75–100 danger.
Это наблюдение за вводом, а не определение ИИ; verdict не меняется.

## Реализация

- `packages/contracts/src/paste-evidence.ts`: карта версии 1, UTF-16,
  base64 битовой маски (младший бит первым), и Staff `pasteEstimate`.
- `packages/offline/src/text-origin.ts`: редактирование и ограниченная
  история undo/redo; `written-submission-draft.ts` сохраняет текст и карту
  атомарно. `written-submission-outbox.ts` фиксирует снимок отправки.
- `apps/student/src/student-written-submission.tsx` и
  `packages/product/src/submission-composer.tsx`: общая информация о
  фактическом вводе. `onTextPaste` composer сообщает длину только после
  состоявшегося input, а отменённое событие не увеличивает счётчик. Замена сохраняет происхождение прежнего текста.
- `models/pwa/paste_evidence.py`, migration 0119 и существующие API/DB
  письменных сообщений: валидация, хранение и оценка.
- `packages/product/src/paste-evidence-badge.tsx`: плашка; Staff workspace,
  evidence и история подключают её отдельно к каждому тексту.

Повреждённая карта в локальном черновике сбрасывается до грубой оценки,
сохраняя текст решения. JSON-body допускает дополнительные 32 КиБ для карты.

Бит 1 означает вставку. Длина карты равна JS `text.length`; лишние биты
последнего байта нулевые. Пробелы, переносы строк и собственные вставки
учитываются. Промежуточные версии и буфер обмена отдельно на сервер не
отправляются. Карта восстанавливается после reload/offline и передаётся
только владельцу Student для подготовки замены; Family её не получает.

Старые непустые черновики и entries без карты используют прежнюю сумму
вставок / длину текущего текста, максимум 100%. Полное очищение черновика
начинает новый учёт. Telegram и фотографии без текста не имеют оценки.
Процент округляется до ближайшего целого, ненулевая доля — минимум 1.
История undo/redo ограничена 100 изменениями и 5 МиБ; недоступный снимок
переводит карту в неизвестное состояние с грубой оценкой.

Backend принимает прежние запросы без нового поля. Их idempotency-хеш
остаётся прежним. Выпуск: migration/backend перед frontend.

## Проверка

Проверить целиком вставленный ответ, смешанный ввод, удаления и замену
выделения, отменённую вставку, undo/redo, emoji, reload, outbox/retry,
замену entry, перенос и старые данные. Unit/Storybook плюс E2E на настоящем
aiohttp; gate: `make pwa-check-fast PWA_E2E_MODES="review submissions"`.

Статус: интегрировано в актуальную `vmshpwa`, включая проверку простынёй и просмотр фото.
Общий `make pwa-check-fast PWA_E2E_MODES="review submissions student-results"`
прошёл без исключений: 2997 Python / 6 SKIP, 1117 frontend, 378 Storybook,
10 Chromium E2E. Корпуса уже находились в основном checkout; копирования не было.
[Квитанции интеграции и выпуска](../../pwa_tests/reports/paste-evidence-20261011/README.md).

`ReviewSheetCard` передаёт оценку в временное сообщение, пока подгружается история;
[регрессия](../apps/staff/src/review-sheet-page.test.tsx) проверяет одну плашку до и
после загрузки. Миграция 0119 применяется до frontend. Второй production использует
[guarded deploy](../../docs/deploy/tlf-app/deploy_paste_evidence.sh) и
[private check](../../docs/deploy/tlf-app/paste_evidence_check.py): backup, up/down/up
на серверной копии, остановка writers, сравнение существующих строк и сохранение
конфигурации/NATS. Владелец разрешил оба production-выпуска 11 октября 2026.

Выпущено на оба production: `bef85d3c8d5e`, schema 0119; [проверка и сохранность данных](../../pwa_tests/reports/paste-evidence-20261011/production-proof.json).
