# Phase 11: production-build browser checkpoint

Дата: 30 июля 2026 года.

## Среда

Все прогоны использовали один loopback origin, настоящие production bundles,
aiohttp и заново seeded `pwa-e2e` SQLite. MSW, Telegram, Google, S3 и human
runtime не подключались. Проверялись Chromium, WebKit и Firefox.

## Результаты

### Полный прогон

Команда `make pwa-e2e`:

- `197 passed`;
- `6 skipped` по заранее заданной browser matrix;
- `4 failed`;
- длительность — 2,7 минуты.

Три ошибки относятся к одному visual test `@visual student current week`.
Baseline изображает прежнюю одно-курсовую страницу высотой 1188 px, тогда как
текущая production-сборка стабильно показывает принятую многокурсовую структуру
высотой 966 px. Baseline не обновлялся: по правилам проекта новый snapshot
должен сначала принять владелец дизайна.

Четвёртая ошибка — Firefox content publication flow. После cold-offline
checkpoint повторная навигация завершилась browser-native `NS_ERROR_FAILURE`;
retry дошёл дальше, но тест жёстко ожидал подпись `Revision 1`, хотя предыдущая
неудачная попытка уже создала revisions 1–2.

### Functional-only прогон

Команда `make pwa-e2e-functional` завершилась с кодом 0:

- `192 passed`;
- `6 skipped`;
- `3 flaky`;
- длительность — 2,6 минуты.

Все три flaky относятся к realtime assertions. Параллельные реальные product
flows публиковали корректные `invalidate` тому же seeded Student, а старые
assertions ожидали строго `['connected']` либо ровно два сообщения
`connected + pong`. Retry прошёл; это недостаточная изоляция тестовых событий,
а не потеря invalidation или reconnect.

Изолированный `make pwa-e2e-realtime` затем прошёл **12/12** в трёх браузерах
без retry.

### Изолированный content-прогон

Команда `make pwa-e2e-content`:

- Chromium: PASS;
- WebKit: PASS;
- Firefox: FAIL.

На первой Firefox-попытке сценарий дошёл до rollback, но нажатие
«Откатить опубликованное» не показало inline-подтверждение; ожидание кнопки
«Подтвердить» закончилось по 90-секундному timeout. Повторные попытки после
этого упёрлись в уже описанную жёсткую подпись `Revision 1` при фактических
`Revision 3` и `Revision 5`.

## Вывод и незакрытые gate

Ни product-код, ни E2E-код, ни snapshots в рамках этого checkpoint не
изменялись. Функциональная матрица в целом работает, но Phase 11 browser gate
нельзя назвать полностью зелёным до трёх отдельных действий:

1. владелец визуально принимает новую Student «Сейчас», после чего snapshot
   обновляется осознанно;
2. Firefox rollback исследуется и получает отдельный устойчивый сценарий;
3. realtime assertions перестают считать постороннее валидное `invalidate`
   ошибкой либо получают раздельных seeded principals.

Transient screenshots, traces и error contexts находятся в
`vmshpwa/test-results/` и не коммитятся. Этот отчёт намеренно не превращает
retry в PASS и не скрывает browser-specific blocker.
