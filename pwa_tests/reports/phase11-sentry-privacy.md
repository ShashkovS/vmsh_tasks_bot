# Phase 11: privacy boundary для Sentry

Дата: 30 июля 2026 года.

## Результат

Frontend и aiohttp/Telegram runtime инициализируют Sentry без автоматической
передачи персональных данных. Перед отправкой события дополнительно очищаются:

- user context;
- cookies, headers, request body и server environment;
- query string и fragment URL;
- ответы, комментарии, тексты, токены, Telegram-данные и сведения о вложениях;
- публичные URL фотографий решений (`/sol_imgs/`);
- текст console/log и UI-interaction breadcrumbs.

PWA runtime читает DSN и release только из явных `VMSH_SENTRY_DSN` и
`VMSH_SENTRY_RELEASE`. Для этого не загружаются Telegram- или Google-настройки.
Release передаётся в Sentry и позволяет отличить frontend/backend revision при
откате.

Реализация:

- `vmshpwa/packages/app-shell/src/observability.ts`;
- `helpers/pwa/sentry_safety.py`;
- `helpers/config.py`;
- `vmshpwa/.env.example`.

Это соответствует штатной модели Sentry: `beforeSend` фильтрует событие перед
отправкой, а `beforeBreadcrumb` может изменить или отбросить автоматически
собранный breadcrumb. Использованы только эти поддерживаемые hooks, без
дополнительного transport-wrapper:

- <https://docs.sentry.io/platforms/javascript/guides/svelte/enriching-events/breadcrumbs/>;
- <https://docs.sentry.io/pdfs/developer-quick-reference-guide.pdf>.

## Проверки

- frontend privacy unit tests: `2 passed`;
- backend config/auth/privacy focused suite: `30 passed`;
- отдельный historical Telegram policy suite: `26 passed`;
- полный frontend unit suite: `102 files`, `561 passed`;
- полный Python suite: `1474 passed`, `4 skipped`;
- production build Student/Family/Staff и двух service workers: PASS.

Тесты проверяют не только чистые функции, но и параметры фактической
инициализации SDK: `send_default_pii=False`, три privacy hook и release.

## Граница доказательства

В настоящий Sentry project тестовое событие не отправлялось: в agent runtime нет
выделенного test DSN, а отправлять синтетические данные в production project
нельзя. Поэтому проверены локальная политика и wiring, но не alert delivery,
retention и настройки доступа самого Sentry project. Эти пункты требуют
отдельного test project или явного production rehearsal владельцем.
