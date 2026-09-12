# Phase 8 proof: due-time invalidation локальных новостей

Дата проверки: 3 августа 2026 года.

## Реализовано

- Существующий пятисекундный content scheduler проверяет окно
  `(lastSuccessfulScan, now]` для visible local news.
- Если в окне есть хотя бы одна публикация, Student, Family и Staff получают
  один `local-news-published` refetch hint для `news` и
  `notification-events`.
- Скрытая до срока публикация не создаёт hint. Повторное окно не включает уже
  обработанную границу.
- Watermark двигается только после успешного DB read и broker publish; временный
  сбой повторяет то же окно.
- Отдельная таблица, lease и durable NATS-state не добавлены. Два worker могут
  послать одинаковые idempotent hints; SQLite/read API остаются источником
  истины.

## Доказательства

- `pwa_tests/integration/test_phase8_news_moderation.py` проверяет три audience,
  точные resource/reason, неповторяющееся следующее окно и отменённую
  публикацию.
- `pwa_tests/test_pwa_content_scheduler.py` проверяет периодический вызов и
  непрерывность successful scan windows, а также штатный shutdown.
- `pwa_tests/test_pwa_app.py` сохраняет общий WebSocket/invalidation contract.
- Focused regression: **52 PASS** в восьми workers.
- Полный PWA Python gate после объединения с соседним news-edit срезом:
  **1578 PASS / 6 intentional skips** в восьми workers за **67,20 с** pytest
  time.
- Ruff format/check и `git diff --check`: **PASS**.

## Границы

- Погрешность foreground update — не больше обычного scheduler interval
  (пять секунд), если SQLite и broker доступны.
- Duplicate hint от двух worker допустим: он не содержит content и вызывает
  только повторный authoritative GET.
- При рестарте старые публикации специально не replay-ятся; все WebSocket
  reconnects уже требуют полный resync.
- Этот proof не заменяет Web Push delivery и не доказывает browser visual gate.

Runbook: [`vmshpwa/docs/local-scheduled-news.md`](../../vmshpwa/docs/local-scheduled-news.md).
