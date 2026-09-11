# Работа с задачами: проверка

[Требования и реализация](../../../vmshpwa/docs/task-interaction-polish.md).

- E2E: **6 passed**, Chromium / WebKit / Firefox. [Новый сценарий](../../../vmshpwa/e2e/task-interaction-polish.spec.ts): полные номера, закрытый листок без ответов, возврат к отдельному листку и к десятому подгруженному занятию, поле на 320/390 px, «Отправляем…», задержка и подтверждение настоящей посылки после перезагрузки. [Регрессия печати](../../../vmshpwa/e2e/worksheet-print.spec.ts): раскрытые материалы, скрытые ответы и переписка, обе темы, изображения и PDF.
- Backend: последний прогон `test_task_titles.py`, `test_review_series.py`, `test_content_http_api.py` — **56 passed**. В предыдущем прогоне также прошли `test_content_repository.py`, `test_live_marking.py`, `test_student_results.py` (48 тестов). Подтверждены подписи для Student/Family/Staff и различение черновика, отправленного ответа, архивной переписки и оценки без посылки.
- Компоненты, outbox и контекст листка: **34 passed**; интерактивная история `WrittenComposer` — **1 passed**.
- Сборка всех приложений, workspace/tools typecheck, ESLint изменённых файлов. В журнале сборки остаются прежние предупреждения о размерах chunks и SymPy deprecation.

E2E выполнялся через `exclusive_e2e_run` / `run_commands` со сборкой всех приложений и чистым `pwa-e2e` backend. Задержка проверяется при заблокированном Service Worker (для перехвата WebKit); API не подменяется. Печатный сценарий работает с обычным Service Worker. Закрытые листки создаёт [изолированный seed](../../../vmshpwa/scripts/seed_e2e_worksheet_print.py), без перевода часов браузера и изменения пользовательских данных.

## Снимки

| Браузер | 320 px | 390 px | Задержка отправки |
| --- | --- | --- | --- |
| Chromium | [Поле](chromium-composer-320.png) | [Поле](chromium-composer-390.png) | [Ожидание](chromium-delayed.png) |
| WebKit | [Поле](webkit-composer-320.png) | [Поле](webkit-composer-390.png) | [Ожидание](webkit-delayed.png) |
| Firefox | [Поле](firefox-composer-320.png) | [Поле](firefox-composer-390.png) | [Ожидание](firefox-delayed.png) |
