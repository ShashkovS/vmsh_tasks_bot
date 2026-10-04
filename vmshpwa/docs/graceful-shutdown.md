# Завершение дочернего SymPy worker — 4 октября 2026

## Причина и исходный замер

Владелец попросил добавить graceful shutdown дочерним процессам PWA.
При выпуске рисунков остановка TLF заняла 75 с: Gunicorn workers завершились
за 1 с, master ждал 30 с, systemd ещё 45 с до SIGKILL двух `ThreadPoolExecu`.
[Исходное доказательство](../../pwa_tests/reports/combined-optimization-figures-20261004/production-proof.json).

Диагностика `/proc` и кода установила источник: `helpers/checkers.py` создаёт
ленивый `mathsolvers.MathWorker`. Символьные ответы PWA проверяются через
`models/pwa/submissions.py` и `db_methods/pwa/submissions.py` в thread executor.
На Linux библиотека выбирает `fork`, поэтому child наследует имя потока,
Gunicorn sockets, signal handlers и SQLite lifecycle locks. В `main.py`
`worker.shutdown()` вызывался только для `legacy`; PWA пропускал этот шаг.
`asyncio.all_tasks()` не охватывает multiprocessing children.

## Решение и план

1. Выбрать `spawn` для SymPy worker: не наследовать серверные descriptors и
   Gunicorn signal handlers. Сохранить ленивый запуск и прежние checker timeouts.
2. Сериализовать протокол единственного SymPy pipe и его закрытие в
   `helpers/checkers.py`; завершать через существующий sentinel, join/reap,
   закрывать оба pipe и process handle. Force kill остаётся только fallback.
3. В `main.py` закрывать уже загруженный worker в aiohttp cleanup context,
   после drain HTTP handlers и SQLite executors. Не импортировать/создавать
   новый MathWorker при cleanup приложения, которое не использует checkers.
4. Проверить настоящий child и двухworker Gunicorn с SIGTERM, завершение
   активного запроса, отсутствие orphan processes, закрытые descriptors и
   неизменность checker verdicts. Затем один fast gate с Chromium submissions.
5. Выпустить на оба production; зафиксировать замеры и services/HTTP checks.
   Первый restart ещё останавливает старый код; новый shutdown проверяется
   отдельно на изолированном runtime, без production accounts/data.

## Статус

Реализация и backend-проверки завершены: 2791 уникальный Python PASS /
7 SKIP (полный набор плюс повтор изменённого файла), 8 реальных process tests.
Fast gate прошёл за 203 с: 1028 frontend, 355 Storybook, 3 Chromium submissions,
types/lint/i18n/format/dependencies. После backend-дополнений frontend не менялся
и повторно не проверялся. Локальный двухworker Gunicorn с двумя SymPy children
выходит за 1,169 с без SIGKILL. Linux TLF preflight: 8 PASS за 10,65 с, shutdown — 1.891 с. Выпуск — следующий шаг.
[Измерения, границы проверки и deploy script](../../pwa_tests/reports/graceful-shutdown-20261004/README.md).

Child boundary: `helpers/math_worker_process.py` устанавливает TERM handler
и readiness packet; `helpers/math_worker.py` сохраняет mathsolvers packet/verdict
protocol и одноcекундный deadline после готовности SymPy. Cold import не входит
в бюджет вычисления. Все принятые checker calls завершаются перед закрытием;
новые вызовы после cleanup не могут заново создать child. Новое приложение
открывает lifecycle заново через `resume_worker()`.
