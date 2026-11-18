# Phase 8C: Web Push subscription backend proof

Дата: 2026-07-29.

## Граница среза

- Migration `0064.pwa_push_subscriptions` хранит browser subscription, текущую auth session и ключи шифрования.
- `db_methods/pwa/push_subscriptions.py` содержит три прямые SQLite-операции: save, delete и будущую выборку для доставки.
- Формат HTTPS endpoint, P-256 public key, auth secret и expiration time проверяются в `models/pwa/push_subscriptions.py`.
- Русские сообщения и HTTP status находятся только в `apps/pwa_api/push_subscription_routes.py`.
- Student и Family получают authenticated config/register/delete endpoints; Staff route отсутствует.
- VAPID-настройки читаются только из окружения PWA runtime. Private key не попадает в ответ или repr config.
- Шифрование и отправка Web Push, retry и service-worker UI не входят в этот срез.

## Проверяемое поведение

- migration проходит up/down/up и `PRAGMA integrity_check`;
- повторная регистрация того же endpoint обновляет одну строку и сохраняет public ID;
- HTTP endpoint требует действующую Student/Family session и настроенный public VAPID key;
- delete ограничен account ID, поэтому Family не удаляет Student subscription;
- небезопасный HTTP endpoint и некорректные browser keys отклоняются до SQL;
- выключенный Web Push не мешает запуску PWA API и отвечает явным `push_not_configured`.

## Результаты

- Ruff and Python compile: passed.
- Focused migration/model/HTTP tests: 4 passed.
- Push + notification + PWA app factory regression set: 50 passed.
- Schema inventory check: 379 objects, SHA-256 `cda08a14972a3167b0961491f38e7481d7a4e3fea6fc15945473c8aee085f818`.
- `git diff --check`: passed before staging.

## Следующий срез

Shared browser contract/client, contextual permission request and Student/Family service-worker push/click handling. Server delivery remains a later independent commit.
