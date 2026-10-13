# RAM-кеш чтений воркера

Решение владельца 12.10.2026 после [аудита](2026-10-12-analysis.md): хранить
общие занятия, задачи и материалы в словарях каждого Python worker; сбрасывать
после публикации через broadcast NATS. Auth/grants могут отставать до 15 минут.
S3 для backups — отдельный следующий шаг.

Реализация: [WorkerReadCache](../../helpers/pwa/read_cache.py),
[CachedContentRepository](../../apps/pwa_api/read_cache.py),
[PwaAuthService](../../apps/pwa_api/auth_service.py),
[составление приложения и NATS](../../apps/pwa_app.py).

- Общие scope, страницы/карточки занятий, публикации и список задач кешируются
  лениво; один miss обслуживает параллельные запросы. LRU: 4096 записей,
  приблизительно 64 MiB графа Python на worker. Не требуется читать весь архив
  при запуске. Mutable AST выдаются копиями.
- Персональные verdict/queue/discussion/answer/reveal/consent читаются отдельно
  из БД при каждом запросе. Изменения через Telegram также сразу видны.
- Существующие события публикации, скрытия, расписания, блоков и problem release
  сбрасывают lesson и страницы; banner/live-results не сбрасывают общий материал.
  Локальный сброс предшествует publish, даже если NATS не доставил событие.
  Переподключение очищает кеши; при недоступном broker общий кеш обходится.
  TTL 5 минут страхует пропущенные Core NATS события и legacy/admin изменения.
- Branding/default locale/support email также хранятся в worker dictionary
  на 15 минут; изменение профиля сбрасывает все workers. Поэтому warm
  `/auth/me` больше не выполняет скрытое чтение branding.
- Auth cache: максимум 8192 записей / 32 MiB, TTL до 900 секунд и до expiry
  cookie/session. Ключ — audience, account/session и версии, trusted signing time.
  Подпись проверяется всегда; ошибки и отсутствующие сессии не кешируются.
  Refresh читает БД; logout/session-control и изменение locale очищают кеш.
  Смена активной группы/режима также сбрасывает auth для ученика и семьи.
  Правки названия, дедлайна и опубликованных metadata сбрасывают общий материал.
- Invalidation generation запрещает старому in-flight чтению восстановить кеш;
  отмена одного waiter не отменяет чтение другого. Фоновые cache tasks отсутствуют.

Проверки и состояние: [STATUS](STATUS.md), [выпуск на оба портала](worker-read-cache-release.md).
Замер новых HTTP percentile под нагрузкой выполняется после release;
кеш не устраняет тяжёлые live-board SQL.
