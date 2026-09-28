# Анализ производительности

- 2026-09-27: read-only аудит завершён. [Отчёт](2026-09-27-analysis.md),
  [агрегаты Prometheus](2026-09-27-prometheus.json),
  [маршруты](2026-09-27-routes.csv),
  [запросы для повторения](2026-09-27-prometheus-query.py).
- Выполнены: ресурсы → HTTP/SQLite метрики → доступные journald/Sentry → код →
  приоритеты. Production и пользовательские изменения не менялись.
- Подтверждены: секундные uploads, эпизодическая read admission queue,
  106 HTTP 500 reveal за измеренное окно. Нет устойчивого насыщения сервера.
- Follow-up: stacktrace reveal; диагностика отсутствия свежих Sentry событий;
  полный журнал burst с владельцами слотов; stage timings конверсии/storage;
  изолированный benchmark вариантов readers и reconnect fan-out.
- Ограничения: SSH разрешает последние 100 строк journald, nginx access.log
  недоступен; текущий фрагмент совпал с deployment. Историческую первопричину
  очередей и разбивку upload времени нельзя подтвердить имеющимися данными.

- 2026-09-27, follow-up: по решению пользователя убран повторный SHA256 при
  выдаче письменных фото всем аудиториям в `written_submission_routes.py`.
  Проверки доступа, размера/type и upload validation сохранены. Выполняется
  проверка существующих HTTP сценариев; S3 GET и кеширование не меняются.
- Проверка удаления read-time SHA256: 7 существующих HTTP тестов written/
  attachment прошли, включая student/family/staff и отказ без авторизации.
  Первый запуск был заблокирован sandbox на bind локального сокета; повтор с
  разрешёнными локальными сокетами успешен. `git diff --check` прошёл.
- Следующее обсуждаемое улучшение: прямая выдача обработанных фото из S3 по
  короткоживущим подписанным URL после проверки доступа; ещё не реализовано.
- 2026-09-27: реализуется [прямая выдача фото](photo-delivery.md) через 302 на
  S3 URL с TTL 86400 по решению пользователя. Stable mediaPath обновляет ссылку
  при повторном запросе; backend не читает объект. Проверяются signing и HTTP.
- Gate пройден: 32 теста S3/written HTTP PASS, `git diff --check` PASS.
  Read-only проверка production nginx: bucket origin Beget уже разрешён в
  img-src/connect-src. Сервер и bucket не изменялись; нужен обычный backend release.

- 2026-09-27 incident: production 34af1445 включает unconditional photo 302.
  Найдена несовместимость: WrittenMaterialReassignmentClient и
  WrittenSubmissionClient используют Blob fetch с redirect:error. Это упущено
  в исходной проверке. Hotfix: S3 redirect только для Sec-Fetch-Dest:image,
  Sec-Fetch-Mode:no-cors; fetch/CORS/старые клиенты снова получают 200 с байтами.
  Повторное SHA256 не возвращается. Выполняется HTTP regression перед выпуском.

- Incident hotfix gate: 32 S3/written HTTP PASS, diff-check PASS; готов к
  выпуску. Проверка deployment и возврата media 200 выполняется после push.
- Hotfix 2504acb0 отправлен и выпущен 27.09 в 12:52:52 UTC. Deploy log:
  frontend=false, backend=true, migrations=false; все runtime/ready и metrics
  health checks PASS, service active, NRestarts=0. Frontend symlink остаётся
  на 34af1445: это ожидаемый backend-only выпуск. Пользовательский browser smoke
  пока не подтверждён; интерфейс нужно обновить для повторной загрузки фото.

- 2026-09-28: завершена read-only [проверка перед нагрузкой](2026-09-28-readiness.md).
  [18h baseline](2026-09-28-baseline.json) сохранён. Обычные API p95 88–175 мс,
  очередь read peak 23/worker, устойчивого насыщения ресурсов нет. Reveal всё
  ещё даёт 59 HTTP 500 за окно. Prometheus rules пусты; доступ к полному journald
  остаётся главным ограничением вечернего анализа. Новые metrics/alerts и
  изменения runtime не выкатывались; предложения и границы проверки в отчёте.
- 2026-09-28 instrumentation increment: media stages с фиксированными labels,
  loop lag histogram/live worker gauge и rate-limited frontend failure event
  через существующую аналитику. Без payload/URL, без дополнительного Sentry,
  без новых фоновых таймеров. Проверки и подготовка экспорта журнала выполняются.

- Instrumentation gate: 147 Python и 23 frontend tests PASS, ESLint/typecheck PASS.
  [Документация](2026-09-28-instrumentation.md), alert rules (promtool PASS) и
  exporter (bash -n PASS) подготовлены; alerts/export не активированы.
- Vite production builds staff/student/family PASS (предупреждения о размере chunks).
