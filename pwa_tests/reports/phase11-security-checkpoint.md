# Phase 11: security checkpoint

Дата: 30 июля 2026 года.

Это исполняемый checkpoint уже реализованных границ, а не внешний pentest и не
окончательное принятие production-конфигурации.

## Выполненные проверки

Отдельный набор из 295 тестов прошёл полностью. Он включает:

- exact Origin/Referer и Fetch Metadata для cookie mutations;
- одинаково строгую защиту login до появления сессии;
- audience-scoped cookies, refresh rotation/replay, revoke и logout-all;
- WebSocket origin, активную сессию, revoke во время handshake и закрытие уже
  открытого соединения;
- trusted-proxy boundary для прямого TCP, одного доверенного proxy и Unix
  socket; клиентские `Forwarded`/`X-Forwarded-*` не становятся доказательством;
- строгую конфигурацию signing keys, peppers, public origins и production
  secure cookies;
- CSP и остальные security headers aiohttp и nginx template;
- nginx login limit `6r/m`, burst 4, `429` и `Retry-After: 60`;
- deny-by-default routing API/WS/static paths и GET-only media proxy;
- raster/HEIC/TikZ conversion boundaries, WebP metadata removal, размер,
  timeout и очистку временных файлов;
- fail-closed answer checker, redacted failures и совместимость Telegram/PWA;
- public/private object-storage URL validation и отсутствие credentials в
  безопасном `repr`/ошибках.

Дополнительные сквозные доказательства на том же tree:

- полный PWA regression: `559` frontend unit и `1 463` Python tests passed,
  `3` Python tests intentionally skipped;
- production-build functional E2E: `194 passed`, `6` intentional skips во всех
  трёх browser engines; один WebKit reconnect assertion был исправлен после
  обнаруженной ложной нестабильности;
- historical Telegram regression: `44 passed`.

## Зафиксированные границы риска

- `cor_ans_checker` остаётся исполняемым Python только для доверенного admin.
  Allowlist и fail-closed обработка уменьшают случайный ущерб, но это явно не
  security sandbox. Право редактирования checker-кода нельзя выдавать обычному
  teacher.
- Фотографии решений доступны по длинному публичному URL. Это принятое
  продуктовое решение: URL нельзя считать секретом после передачи третьему
  лицу; listing bucket должен оставаться закрытым, а ключи — непредсказуемыми.
- API CSP строже browser CSP. Финальный browser CSP задаёт nginx и разрешает
  только один media origin, один optional Sentry ingest origin и WebSocket того
  же public host.
- Ограничение перебора логина находится в nginx, поэтому aiohttp unit/E2E не
  доказывают работу реального production rate limiter.

## Открытые production-gates

- выбрать production FQDN/media/Sentry origins, отрендерить template и
  выполнить настоящий `nginx -t` на сервере;
- проверить headers и spoofed proxy requests через реальный nginx → gunicorn
  Unix socket;
- выполнить dependency vulnerability review по итоговым lock-файлам;
- проверить Sentry redaction реальным синтетическим событием без приватного
  содержимого;
- провести ручной review IDOR для окончательного списка маршрутов и ролей;
- подтвердить, что production admin-доступ к checker editor защищён именно
  серверным permission check, а не только скрытием UI.

До этих действий checkpoint не обозначается как финальный security sign-off.
