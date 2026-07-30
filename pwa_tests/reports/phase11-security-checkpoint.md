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
- серверную admin-only границу для редактируемого
  `cor_ans_checker`: content metadata требует `content.manage`, повторная
  проверка попыток — `checker.manage`; оба capability выдаются только
  legacy-admin и не появляются у teacher через staff scope;
- public/private object-storage URL validation и отсутствие credentials в
  безопасном `repr`/ошибках.

Граница checker проверена на том же пути, который использует production
API, а не только скрытием UI:

- `apps/pwa_api/content_routes.py`: `GET/PUT .../metadata-grid` вызывают
  `_staff_actor`, требующий `Capability.CONTENT_MANAGE`;
- `apps/pwa_api/submission_routes.py`: preview/apply повторной проверки
  требуют `Capability.CHECKER_MANAGE`;
- `helpers/pwa/permissions.py`: оба capability входят в
  `_ADMIN_ONLY_CAPABILITIES`;
- `pwa_tests/test_permissions.py` проверяет матрицу и то, что admin-scope
  не повышает legacy-teacher;
- `pwa_tests/integration/test_content_http_api.py::test_staff_problem_matching_and_metadata_grid_http_workflow`
  проверяет `403` для teacher в том же content workflow;
- `pwa_tests/integration/test_phase10_problem_import_preview.py` проверяет
  `403` для teacher на preview/apply XLSX-import.

Узкие прогоны 30 июля 2026 года: `79 passed` для permissions +
content HTTP workflow и `3 passed` для admin-only import/rollback. Единственное
предупреждение в обоих запусках — уже известная deprecation-warning из
зависимости `mathsolvers`; тесты завершились успешно.

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
  содержимого.

Ручной IDOR/role review закрыт отчётом
[`phase11-idor-role-review.md`](phase11-idor-role-review.md): `154 passed`,
без найденных bypass; различие `403`/`404` для некоторых Staff detail
routes зафиксировано как принятый низкий риск без выдачи данных.

До этих действий checkpoint не обозначается как финальный security sign-off.
