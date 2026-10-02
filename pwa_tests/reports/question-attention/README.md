# Индикаторы вопросов: проверка 1 октября 2026

Реализовано локально по [принятому плану](../../../vmshpwa/docs/question-attention.md).
Production-выпуск не выполнялся. Существующие сообщения, версии переписки и история
сохраняются; серверные отметки индивидуальны для ответа и общие для устройств ученика.

## Проверки

- Backend: 38 целевых тестов (`test_support_attention`, `test_support_thread_http_api`,
  `test_phase8_support_notifications`, `test_schema_inventory`) — PASS.
  Up/down/up, старые ответы, teacher/admin, атомарная проверка владельца и треда,
  повторные отметки, несколько ответов, системные сообщения, ответ во время
  подтверждения другого ответа, публикация/доступ, сортировка и цикл между группами.
  После переноса SQL уведомлений в `db_methods/pwa` повторены связанные тесты.
- Изоляция E2E: 11 тестов runner/seed — PASS; отдельный seed дополнительно проверен
  через настоящий `PwaAuthRepository`, включая grant активной группы.
- Frontend: общий прогон — 978 PASS и один таймаут ESLint guard под нагрузкой;
  отдельно этот guard и изменённые контракты/клиент/видимость/лента — 25 PASS.
  Затем граничная видимость 75%, offline reset и URL-параметр — 7 PASS.
  Новые данные совместимы со старыми payload; GET не отправляет read-запросов.
- `make pwa-e2e-support` — **6/6 PASS**, без retries: Chromium, Firefox, WebKit.
  Два независимых Student-устройства, настоящий Staff-ответ, warning → danger,
  глобальная кнопка из другого курса/группы, загрузка старого листка, первый
  непрочитанный ответ, серверное подтверждение и исчезновение счётчика на обоих
  устройствах, перезагрузка ссылки. Дополнительный ответ проверен в EN, dark,
  320 px и reduced motion (computed animation-name = none).
- Chromium Storybook: Waiting / Unread / Read — 3/3 PASS, addon-a11y в error mode.
- Все четыре приложения успешно собраны production Vite build в E2E runner.
  `make pwa-typecheck pwa-i18n-check pwa-lint` — PASS; после правок E2E ещё раз
  проверены tools TypeScript и scoped ESLint. Lingui extract выполнен, RU/EN
  переводы заполнены; backend i18n check — PASS.
- Scoped Prettier, Ruff и `git diff --check` — PASS.
- `make pwa-schema-check` — PASS: 500 объектов, SHA-256
  `9a7b5fa26427d16aff03aad146448080acde73b6635bdd20f5313bf2536c39b8`.

Общий Python-прогон `uv run pytest -q -n4 pwa_tests --tb=short`: 2493 PASS,
6 SKIP, 5 FAIL. Проверка числа объектов схемы обновлена до 500 и повторно
прошла. Четыре оставшихся ошибки относятся к `test_content_characterization`
и `test_legacy_golden_corpus`: существующий `_vmsh_examples/.DS_Store`
не соответствует строгому корпусу. Посторонний файл сохранён согласно AGENTS.md;
код и manifest старого корпуса не менялись. Полностью зелёный общий backend gate
поэтому не заявляется.

## Снимки

Вручную просмотрены danger в светлой теме и переписка в тёмной теме на 320 px
во всех трёх движках. Снимки из успешного финального прогона:

| Движок | RU, danger | RU, read, dark | EN, unread, dark, reduced motion |
|---|---|---|---|
| Chromium | [точка](chromium/question-unread-indicator.png) | [переписка](chromium/question-read-dark-320.png) | [переписка](chromium/question-unread-dark-en-reduced-320.png) |
| Firefox | [точка](firefox/question-unread-indicator.png) | [переписка](firefox/question-read-dark-320.png) | [переписка](firefox/question-unread-dark-en-reduced-320.png) |
| WebKit | [точка](webkit/question-unread-indicator.png) | [переписка](webkit/question-read-dark-320.png) | [переписка](webkit/question-unread-dark-en-reduced-320.png) |

## Порядок выпуска

1. Сделать штатный backup и применить `0107.pwa_support_entry_reads` к SQLite.
   Baseline миграции отмечает только существующие Staff-ответы, не меняя записи
   переписки. Проверить schema inventory и integrity/FK gate штатного deploy.
2. Выпустить backend с read/attention API и realtime-инвалидациями. Старые клиенты
   продолжают получать прежний payload, новые используют capability-header.
3. Выпустить frontend и выполнить штатный production HTTP smoke и короткую
   проверку нового ответа/прочтения на двух устройствах.

Этот отчёт подтверждает локальную реализацию и изолированный браузерный gate,
а не применение миграции или работу нового кода на production.
