# Принятые технические решения — 23 июля 2026

Этот документ фиксирует ответы владельца продукта на вопросы после первой версии Storybook. Он дополняет тематические документы в этой папке. При расхождении более позднее явное решение владельца имеет приоритет.

## Математика и content pipeline

- Единственный редактируемый источник условий, подсказок и решений — LaTeX.
- Новый конвертер строится на опыте `_external_pipelines/a16_html_from_tex.py`, `edt_tasks_parser.py`, `mathimg_endpoints.py` и `mathimg_service.py`, но становится тестируемым pipeline с нормализованным промежуточным представлением.
- Web-производная содержит безопасный HTML и исходные LaTeX-выражения. Формулы рендерятся KaTeX на клиенте; CSS и шрифты KaTeX входят в bundle и precache Student/Family PWA.
- У формул нет меню, copy helper, выделения и прочих необязательных интерактивных функций. Семантический MathML KaTeX для assistive technology сохраняется. Печать не снимается с web DOM и использует PDF pipeline.
- Telegram-производная предназначена для `sendRichMessage` Bot API 10.1+ и использует разрешённый Rich Message HTML, включая `<tg-math>` и `<tg-math-block>`. Это не legacy `sendMessage(parse_mode=HTML)`. Ограничения клиента/версии и fallback должны проверяться интеграционными тестами Telegram adapter.
- TikZ остаётся отдельным SVG-object в S3; HTML хранит ссылку и метаданные, а не inline SVG.
- Планируется preview уже сгенерированного PDF. Он не является вторым print renderer и не допускает ручного редактирования производной.

## Object storage и фотографии решений

- Production storage — Hetzner S3-compatible через `aioboto3`; dev/test остаются на filesystem adapter.
- Браузер загружает файл через авторизованный aiohttp endpoint. Presigned browser upload не применяется: офлайн-очередь может ждать существенно дольше жизни подписи.
- Производные работы публично читаются по длинным непредсказуемым ключам. URL нельзя считать авторизацией; в operational logs он редактируется как пользовательский контент.
- Рекомендуемый key: `sol_imgs/user_{user_id}/{season_year}/{lesson_id}/{problem_id}_{created_at_utc}_{uuid}.webp`. Идентификаторы и UUID формирует/проверяет backend, а не браузер.
- До сохранения результата проверки школьник может заменить фотографии. В транзакции фиксации результата текущая revision вложений становится immutable; последующие комментарии и аннотации хранятся отдельно. Физический overwrite существующего object key запрещён.
- Клиент декодирует изображение, уменьшает длинную сторону максимум до 1920 px и сохраняет только WebP. Оригинал не загружается и не хранится. Декодирование/re-encode обычно удаляет EXIF, отдельный EXIF pipeline не требуется.
- HEIC и другие неподдержанные браузером источники сначала пробуются на клиенте, затем отправляются через aiohttp в серверный image service на основе `mathimg_service.py` с ImageMagick/HEIC support. Результат всё равно WebP до 1920 px; исходник остаётся только во временном файле операции.
- Фотографии и история хранятся бессрочно до отдельной политики или ручной чистки bucket. Миграции из `VMSH_MEDIA_ROOT` нет: это новый storage namespace без существующих объектов.

## Authentication и security

- Логин школьника + текущий Telegram token как пароль — финальная совместимая модель, а не временная миграция и не Telegram OAuth.
- Family accounts создаются пакетно в Staff UI одновременно с учениками и связываются на этапе импорта. У родителя отдельные credentials и session.
- Целевая сессия — две audience-scoped HttpOnly cookie: короткая подписанная `itsdangerous` access cookie и ротируемая refresh session в SQLite. Refresh token хранится в cookie только в raw-виде, в БД — HMAC/hash. Отзыв отдельного устройства удаляет DB session.
- Максимальный срок refresh session — ближайшее 10 августа; access cookie существенно короче. У Student, Family и Staff разные имена и `Path`.
- `Secure`, `HttpOnly`, `SameSite=Lax` обязательны. Отдельный synchronizer CSRF token на первом этапе не вводится; unsafe endpoints дополнительно проверяют same-origin `Origin`/Fetch Metadata и принимают только ожидаемый content type.
- Rate limiting выполняет nginx. Как минимум отдельная строгая zone нужна для login/auth; лимиты не заменяют backend authorization или idempotency.
- CSP вводится с первого production deployment. Политика должна явно разрешать собственные scripts/styles/fonts, audience WebSocket/API, Hetzner media origin, Web Push и Sentry ingest; inline/eval не добавляются без документированной причины.
- Аудит чтения чужих работ не нужен. Сохраняются все комментарии учителей, результаты проверки и изменения самой работы. Audit административных изменений, сессий и публикации остаётся.

## Realtime и offline

- Текущий production baseline — два gunicorn worker. NATS обязателен для live fan-out между ними; SQLite остаётся источником восстановления после reconnect.
- Потеря Safari IndexedDB после долгого отсутствия допустима: критических данных только на клиенте нет. Student/Family не более двух раз мягко предлагают установку PWA, без блокирующих экранов.
- Целевой локальный бюджет — около 10–15 MB. Текст условий занимает малую часть; иллюстрации к недавно открытым материалам кешируются примерно на две недели и очищаются LRU/quota policy.
- Logout при непустом outbox показывает предупреждение. После явного подтверждения пользователя локальная очередь и drafts этого аккаунта могут быть удалены.
- Рабочее безопасное допущение каркаса: повтор одного `idempotencyKey` с тем же payload hash возвращает исходный receipt. Другой payload с тем же ключом не побеждает: backend отвечает conflict, сохраняет исходную операцию и требует нового ключа после явного решения пользователя. Владелец продукта ещё должен подтвердить этот UX.
- Дедлайн урока — абсолютный timestamp публикации решений, задаваемый в `Europe/Moscow` и хранимый в UTC. Для offline submission сохраняются client/server timestamps; конкретный порог подозрительного расхождения часов ещё не выбран и остаётся policy-параметром.

## Домен

- Активных уровней сейчас три, но схема, контракты и UI допускают четвёртый и последующие уровни. Цвет назначается по `groups.sort_order`; неизвестные/лишние позиции получают доступный нейтральный fallback.
- Статистика сложности становится видна школьнику после окончания проверки занятия; автоматический grace period фиксирован и равен семи дням, а не является настройкой сезона.
- История группы/уровня/режима сохраняется. Текущий legacy source — `user_changes_log` (`change_type`, `new_value`, `ts`); миграция обязана сохранить и backfill эту историю.

## Frontend

- Sonner удаляется; notification primitives строятся на Base UI Toast.
- Sliding panels строятся на Base UI Drawer, а не на Dialog, замаскированном под Sheet.
- Графики: Visx поверх `d3-array`, `d3-scale`, `d3-shape`.
- Большие Staff grids: TanStack Table + TanStack Virtual.
- Новую DnD dependency не добавляем. Classroom planner может использовать локальную pointer/native реализацию; порядок фотографий меняется удалением и повторной загрузкой в нужной последовательности.
- Формам достаточно собственного малого слоя вокруг Base UI Field/Form semantics.
- Версии общих third-party dependencies задаются pnpm catalog.
- ESLint получает `eslint-plugin-jsx-a11y`; CSS проверяется Stylelint. React Compiler не используется.
- Frontend Sentry включается только при наличии production DSN, без PII. Release/environment/audience передаются как tags; загрузка source maps настраивается серверными secrets позднее.
- Числового coverage gate нет. Тесты добавляются по риску и поведению, а не ради процента.

## Deploy и тесты

- GitHub Actions пока нет. Production обновляется серверным webhook: fetch exact revision, backup SQLite, frozen dependency sync, проверки/сборка изменившихся частей, migrations, controlled restart, healthcheck и detached post-deploy backup.
- Dependency detection учитывает root Python manifests и весь pnpm workspace, включая `vmshpwa/pnpm-lock.yaml`, `pnpm-workspace.yaml` и package manifests.
- Визуальные baselines пока считаются macOS-local artifacts; Docker normalization откладывается. Baseline меняется только после ручной проверки diff.
- Основной E2E остаётся на Vite dev servers с настоящим aiohttp для скорости и диагностики. Production build остаётся отдельным обязательным gate; deploy выполняет короткий smoke уже собранных assets и service workers.
- PWA JSON error/request-ID middleware ограничивается `/student`, `/family`, `/staff` API/WS путями и не меняет ответы legacy dashboards.

## Открытые параметры, не блокирующие текущий каркас

- точный допустимый clock skew для offline deadline review;
- финальный UX разрешения конфликта одного idempotency key с разными payload;
- production hostnames для Hetzner bucket, Sentry ingest, API/WS и окончательной CSP;
- короткий access-cookie TTL;
- точная команда/systemd units production webhook;
- выбранное art direction фазы 1.
