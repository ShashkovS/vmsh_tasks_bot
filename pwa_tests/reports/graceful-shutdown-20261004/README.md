# Graceful shutdown SymPy worker — 4 октября 2026

Требование и компоненты: [graceful-shutdown.md](../../../vmshpwa/docs/graceful-shutdown.md).
Исходный production замер TLF — **75 с**: 30 с Gunicorn и 45 с systemd,
два дочерних `ThreadPoolExecu` доживали до SIGKILL.
[Доказательство до изменения](../combined-optimization-figures-20261004/production-proof.json).

Причина: `mathsolvers.MathWorker` лениво fork-ался из потока проверки ответа,
наследовал серверные descriptors/handlers и не закрывался в PWA из-за
legacy-only ветки `main.on_shutdown`. Теперь применяется spawn, собственный
TERM boundary, drain принятых вызовов, sentinel, join/reap и закрытие pipes.
Aiohttp cleanup context завершает worker после HTTP/SQLite drain и выдерживает
повторную отмену. Поздние вызовы не могут создать child после cleanup.
Cold startup ждёт отдельный readiness packet; прежний лимит вычисления 1 с
сохранён, зависшее вычисление kill/reap-ается. Verdicts и packet API сохранены.

## Локальная проверка

`make pwa-check-fast PWA_E2E_MODES=submissions` — **203,306 с PASS**:
2789 Python / 7 SKIP, 1028 frontend, 355 Storybook, 3 Chromium submissions;
types, lint, i18n, format, dependency check и проверенный build cache PASS.
После дополнений к shutdown повторялся только backend, frontend не менялся.

Финальный полный Python: 2790 PASS / 7 SKIP за 172,41 с; один тест отклонил
корректный shutdown за 3,160 с под нагрузкой из-за произвольного порога 3 с.
Убрана эта привязка correctness к производительности; пятисекундный deadline,
exit code 0, отсутствие SIGKILL/WORKER TIMEOUT и проверка исчезновения обоих
child PID сохранены. Повтор всего изменённого файла — **8 PASS за 14,01 с**;
итого 2791 уникальный Python PASS / 7 SKIP. Изолированный двухworker Gunicorn
с двумя активированными SymPy children остановился за **1,169 с**.
[Машинные результаты и source digests](measurements.json).

## Linux и выпуск

Linux preflight выполняется до push на TLF с production Python/Gunicorn и
отдельными test-deps, временными SQLite/media, Unix socket и process group.
Production virtualenv, accounts, БД и сервисы не меняются. Затем
[backend-only deploy](deploy-tlf.sh) сверяет SHA256 всех шести изменённых Python
файлов и переиспользует успешный preflight. Повторной сборки frontend,
установки dependencies или применения migrations нет.

Linux TLF: 8 PASS за 10,65 с, shutdown двухworker Gunicorn — **1.891 с**, exit 0, оба child исчезли без SIGKILL. Выпуск на оба production — в работе. Первый restart
ещё закрывает старый код; его время отдельно от shutdown новой версии.
