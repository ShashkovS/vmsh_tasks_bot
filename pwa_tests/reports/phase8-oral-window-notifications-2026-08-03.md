# Phase 8 proof: уведомление об открытии устного окна

Дата проверки: 3 августа 2026 года.

## Проверяемый результат

- Существующий scheduler создаёт событие `oral_window`, когда активное окно
  действительно открылось. При старте процесса уже открытое, но ещё не закрытое
  окно также подхватывается.
- Получатели определяются в момент открытия по текущему active group и режиму
  `online`. Family и очные школьники событие не получают.
- Повторный проход и второй gunicorn worker безопасны: unique
  `(account_id, category, window_public_id)` не создаёт дубль.
- Payload содержит только публичные IDs и времена. `join_url` и `join_code`
  остаются в no-store join endpoint и в уведомление не попадают.
- После commit foreground получает owner-scoped invalidation. Сбой NATS не
  откатывает durable SQLite event и не запускает повторную запись.
- Категория по-прежнему выключена по умолчанию и появляется только у Student,
  который явно включил её в настройках.

## Реализация

- `db_methods/pwa/oral_windows.py` — короткий interval/startup read;
- `db_methods/pwa/notifications.py` — текущие online Student accounts группы;
- `models/pwa/oral_windows.py` — recipient/payload/dedupe policy;
- `apps/pwa_app.py` — запуск в существующем scheduler и owner invalidation;
- `pwa_tests/integration/test_phase7_oral_windows.py` и
  `pwa_tests/test_pwa_content_scheduler.py` — storage/domain/runtime proof.

## Автоматические проверки

- Ruff затронутых Python-файлов: **PASS**.
- Focused SQLite/aiohttp/scheduler: **11 PASS**.
- Полный PWA Python в 8 изолированных worker’ах: **1588 PASS / 6 intentional
  skips** за 76,53 с.
- `git diff --check`: **PASS**.

Точное упреждение отдельного уведомления `deadline` не угадано: оно вынесено
в вопрос 9 development plan. Physical push-device smoke и owner visual gate
остаются общими внешними gates Phase 8.
