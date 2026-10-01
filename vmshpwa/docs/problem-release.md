# Позадачная публикация

Реализация проверена в отдельном worktree, ветка
`codex/problem-release` от `vmshpwa` (`6a3891f0`).

## Решение

Открытие задач принадлежит занятию группы, независимо от публикации неизменяемого
листка. Все задачи исходно открыты. Один переключатель управляет всем условием
с подпунктами. Off скрывает задачу у всех Student/Family, сохраняя работу и
статистику. Занятие с нулём открытых задач остаётся видимым и сообщает
«Задачи скоро откроются».

Сопоставленные стабильные problem IDs сохраняют состояния между версиями.
Новая задача закрыта, если в текущем занятии есть закрытые задачи; иначе открыта.
Новые подпункты наследуют состояние общего условия. Объединение задач с
разными состояниями закрывает объединённое условие.

Переключения сохраняются сразу, групповые операции атомарны. Конкуренция
проверяется общей версией доступности и ID проверяемого листка. Перед первой
публикацией готовый сопоставленный листок допускает подготовку переключателей.
После публикации редактируется только её текущая версия; другие превью
показывают прогноз состояний.

## Реализация и границы

- [Миграция](../../migrations/0107.pwa_problem_release.sql), механическое
  [хранилище](../../db_methods/pwa/problem_release.py) и
  [доменный сервис](../../models/pwa/problem_release.py).
- [Staff API](../../apps/pwa_api/problem_release_routes.py):
  GET/PUT `/staff/api/v1/group-lessons/{id}/problem-release`.
- [Zod-контракт](../packages/contracts/src/problem-release.ts),
  [StaffProblemReleasePreview](../apps/staff/src/staff-problem-release-preview.tsx)
  и [transport](../apps/staff/src/problem-release-client.ts). Контролы находятся
  в PWA-превью условий; одна строка управляет всем условием с подпунктами.
- [Student offline transport](../apps/student/src/offline-student-data.ts)
  сравнивает `problemReleaseVersion` раньше времени загрузки, чтобы stale
  bundle не вернул известные закрытые задачи.
- Student/Family получают фильтрованные условия, hint/solution, списки и
  счётчики. Telegram, готовый PDF и полная Staff-статистика не фильтруются.
- WebSocket инвалидирует данные после commit, без push/Telegram-рассылки.
  Reconnect восстанавливает состояние из SQLite. Offline показывает последнюю
  полученную версию; известная более новая версия доступности имеет приоритет над старым bundle.
- Off не удаляет черновики или очередь отправки. Новые операции по закрытой
  задаче отвергаются; ранее принятые идемпотентные операции сохраняют receipt.

## Проверка

Пройдены 91 тест SQLite/HTTP (`test_content_repository.py`,
`test_content_http_api.py`, [test_problem_release.py](../../pwa_tests/integration/test_problem_release.py)).
Включены подготовка Off до первой публикации, ноль задач у обеих аудиторий,
запрет нового ответа и reveal, replay принятого ответа, конфликт версий,
новые задачи при закрытом листке и сохранение Off после исправления условий.

Пройдены 975 общих frontend unit-проверок и 46 сфокусированных unit-проверок контентных контрактов/клиента, Staff и offline,
включая [регрессию старого bundle](../apps/student/src/prepare-offline-lessons.test.ts).
[Storybook](../apps/staff/src/staff-problem-release-preview.stories.tsx):
AllOpen (interaction), AllClosed и RevisionPreview — 3/3.
Полный `make pwa-test`: 975 frontend прошли; backend исходно дал 2444 passed
и 17 failures (отсутствующие ignored corpus/config files в новом worktree и
устаревший schema object count). После подготовки отдельной копии ровно
54 утверждённых corpus-файлов, reference pipeline-файлов и пустого локального
config, обновления ожидаемого count 497 → 501 все 17 прошли в повторных запусках
`pytest --lf`. Итого проверены 2461 backend сценарий, 6 skipped. Секреты не
копировались, Telegram polling/Google не запускались; локальные inputs не
входят в commit.

`make pwa-typecheck pwa-i18n-check`, schema inventory, scoped ESLint/Ruff и
четыре production-сборки проходят. E2E запуск: lock-aware
`python -m vmshpwa.scripts.e2e_runner --mode problem-release`, retries 0.
Финальный прогон — 3/3 в 22.9 секундах после сборки/seed. Начало preview
ждёт доступную кнопку; reconnect проверяется после подтверждённого Staff
состояния и допускает штатные таймауты транспорта, без перезагрузки.

[E2E](../e2e/problem-release.spec.ts) с реальным aiohttp: исходная выдача
15 → 0 → 2 → 5 → 15 и обратное скрытие без reload прошли в Chromium,
WebKit и Firefox. Reconnect без reload также прошёл во всех трёх браузерах.
Для WebKit/Firefox с реальным `context.setOffline` дополнительно посылаются
стандартные browser offline/online events: их эмуляция Playwright неполна.
Использована свободная пара loopback-портов 5381/8381: стандартные 5380/8380
заняты параллельной задачей. Временные подстановки только origin/портов и
одноразовые тестовые ключи восстановлены после запуска; стандартная
конфигурация не изменяется. MSW и внешние сервисы в E2E не используются.
Светлые, тёмные и мобильные снимки сохраняются в `vmshpwa/test-results`;
visual baselines не обновлялись. Развёртывание не выполнялось.

## Интеграция с актуальной vmshpwa

1 октября начато вливание `vmshpwa` (`3bb20281`) в `codex/problem-release`.
Сохраняются новые настройки metadata, индекс receipt и редактор рисунков.
[Content workspace](../apps/staff/src/content-page.tsx) объединяет редактор рисунков
и переключатели в одном PWA-превью; фильтрация доступности применяется после
замороженного оформления публикации. Миграция доступности перенумерована в 0107
после 0106 рисунков; schema artifacts генерируются из общей цепочки миграций.
Проверки объединённой реализации в работе.
