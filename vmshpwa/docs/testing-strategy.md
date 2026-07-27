# Стратегия тестирования

## Пирамида

1. Vitest: Zod contracts, query keys, runtime configuration, чистые преобразования, Dexie/outbox и deadline logic.
2. React Testing Library + user-event: редкие изолированные случаи, где DOM integration невозможно надёжно выразить story.
3. Storybook + addon-vitest browser mode: primitives, product components, theme/level/density matrices, loading/empty/error/offline states и interaction tests.
4. Playwright: реальные страницы и aiohttp, base paths/history fallback, runtime API, WebSocket/reconnect, PWA lifecycle, audience isolation и визуальные снимки.
5. Отдельная pytest-регрессия исторических Telegram-сценариев.

## Правила окружения

Unit и Storybook используют MSW 2. Main E2E никогда не использует MSW: Playwright поднимает профиль `pwa-e2e` с отдельной SQLite, media root и NATS prefix. Google и Telegram network calls в новых unit/E2E запрещены. Production build падает при включённом prototype MSW.

`make telegram-history-test` запускает только исторические handler-сценарии с `RecordingBot`, token-shaped заведомо фиктивным значением и без загрузки Telegram/Google credentials. Этот профиль не запускает polling/webhook и не является способом тестировать новый PWA API.

E2E выполняется в Chromium, WebKit и Firefox. Критические mobile Student flows дополнительно получают device projects при появлении реальных submission endpoints. iOS baseline — 16.4, Android — 10. Перед первым production-выпуском обязательна ручная проверка на доступных реальных Android-устройствах; iPhone проверяется по возможности и не блокирует выпуск при отсутствии устройства.

Основной E2E сначала собирает все три production bundles, затем запускает `vite preview` и настоящий aiohttp. Поэтому functional, visual, route splitting, manifests и service-worker проверки видят production CSS/chunks, а не dev/HMR-поведение. Deploy smoke остаётся отдельным коротким контролем уже разложенных сервером assets. MSW не используется ни в одном E2E-режиме.

Перед стартом настоящего aiohttp Playwright вызывает изолированный seed/migration entrypoint. Сам server startup схему не меняет. Python PWA suite создаёт мигрированную временную SQLite отдельно в каждом pytest worker; тесты migration lifecycle дополнительно проверяют пустую/устаревшую/будущую схему, hash drift, WAL, конкурирующих writers и rollback после исключения.

## Visual regression

Снимки страниц хранятся по browser project, делаются при фиксированном viewport, locale, timezone и reduced motion. Сейчас reference environment — macOS машины владельца; Docker normalization откладывается. `pwa-visual-update` не является способом «починить» тест: перед обновлением человек или агент обязан открыть diff, проверить обе темы и убедиться, что изменение ожидаемо. Raw snapshots не меняются вместе с не относящимся к UI refactor.

Отдельный content visual gate сравнивает три реальных листка одного уровня во всех производных представлениях: PWA, Telegram-rich и PDF. Сравнение проверяет формулы, списки, таблицы и SVG/TikZ, а не только общий screenshot страницы.

## Accessibility

Storybook a11y violations имеют status `error`. Проверяются keyboard order, visible focus, accessible names, dialogs/focus trap, таблицы, zoom/reflow, forced colors where applicable и контраст WCAG 2.2 AA. Цвет никогда не является единственным носителем статуса.

Axe baseline действует для Student, Family и Staff. Для Staff обязательны labels, alt, валидный ARIA и контраст; отдельный полноценный keyboard-аналог специализированного gesture/DnD не является самостоятельным требованием. Текущий classroom planner использует обычные select/checkbox controls и поэтому остаётся работоспособным с клавиатуры без специального исключения.

## Definition of done компонента

Публичный общий компонент имеет типы, semantic tokens, stories основных состояний, interaction/a11y test при наличии поведения и краткое назначение. Изменение общего компонента сопровождается обновлением stories; app-specific logic не переносится в `packages/ui`.

Числовой coverage threshold сознательно не вводится. Покрываются contract boundaries, рискованные чистые функции, offline/idempotency logic и наблюдаемое поведение; бессодержательные тесты ради процента не добавляются.

## Начальная приёмка каркаса

- strict typecheck, ESLint, Prettier check, Vitest и Python PWA tests проходят;
- три production bundles собираются, Student/Family создают injectManifest workers;
- Storybook строится и browser tests запускаются;
- Playwright подтверждает shell/base/history/theme/runtime/WebSocket/PWA/audience separation во всех трёх движках;
- Telegram regression запускается отдельной командой.

## Проверки миграции и интеграций

- Migration rehearsal выполняется на копии production SQLite вместе с её `-wal` и `-shm`, если они существуют. Копия никогда не подключается к human/production runtime.
- Производительность и корректность импортов проверяются на production-size копии до применения миграции в production; фиксированный календарный график таких репетиций не нужен.
- Исторические Telegram-сценарии могут дополнительно прогоняться через отдельного тестового бота и тестовый канал. Это изолированный integration profile, не unit/E2E dependency.
- Live profile использует `@vmsh179devbot`; token берётся из `creds_test/vmsh_bot_config_test.json` и не выводится в command/report. Приватный канал отображается как `vmsh179devbot channel`, UI ID `3913815635`, bot имеет admin rights. Probe сначала сверяет `getMe`, затем `getChat/getChatMember` и записывает возвращённый canonical `chat.id` в test `telegram_bindings`; UI ID не преобразуется в `-100…` вручную.
- Владелец разрешил opt-in smoke только в выделенных test resources: disposable S3 prefix `integration/<run-id>/` можно upload/read/public-GET/delete, а test bot может send/edit/delete synthetic messages в приватном test channel. Production bucket, credentials, recipients и учебные каналы запрещены. Classroom delivery hermetic suite использует RecordingBot и проверяет personal recipient resolution без реальных учеников; live smoke отправляет только synthetic test recipient payload.
- В test channel можно публиковать любые synthetic payloads в пределах Telegram limits: граничные Rich Message, formatting, math, tables, media и album cases. Real student data/production media не используются. Report хранит case/request marker, canonical chat ID, returned message IDs и delete/cleanup result при наличии, но не token.
- Live suite запускается явно и последовательно, чтобы тесты не боролись за edit/delete одних сообщений. Обычный `make telegram-history-test`, unit и E2E продолжают использовать RecordingBot без сети.
- Первый content acceptance corpus включает уроки 39, 40 и 41 сезона 2025–2026 для всех трёх уровней; три наиболее показательных листка одного уровня проходят ручное сравнение PWA/Telegram/PDF.
- Classroom unit/domain suite проверяет trim/NFKC/casefold, кириллические дубликаты, archive/restore, inherited layout, optimistic conflicts и свойства алгоритма: комнаты не смешивают группы, прежняя допустимая комната сохраняется, остальные распределяются по наименьшей фактической загрузке. Отдельно проверяются возраст до десятой года, nullable class/strength, aggregates без `NULL`, fuzzy normalization/edit distance и сортировка фамилия+имя.
- Classroom API suite проверяет Teacher `403`, stale `409`, запрет неполного/mismatched plan, атомарный batch move, обязательное подтверждение cross-group change, confirmed history и неизменность прошлых plans. Storybook покрывает catalog/layout/plan states, group markers и `очно/распределено`, 6/5/2 и плотный 15-room/~200-student fixtures, stale/reassigning/no-room, profile missing data, room averages возраста/класса/силы, search/history, bulk mode, local draft restore/conflict и mobile Staff. Отдельная проверка `mobile-staff-layout` требует эти поля в student rows и room headers.
- Classroom Playwright E2E в трёх браузерах создаёт `201` и `Актовый зал`, отклоняет `АКТОВЫЙ ЗАЛ`, подтверждает layout/plan, сверяет Student/Family, скрывает комнату, видит `reassigning`, пересчитывает и подтверждает новую версию. Дополнительно E2E восстанавливает несохранённые select после reload, выполняет bulk и подтверждённый cross-group move, находит фамилию с опечаткой и открывает историю. E2E использует production preview, настоящий aiohttp и seeded SQLite без MSW.
- Draft-persistence suite для Student/Staff проверяет reload/remount, PWA update prompt, account isolation, base-version conflict, explicit discard и очистку только после server receipt. Текст/UI-state проверяются через `localStorage`, blobs/outbox — через Dexie.
- Student/Family progress tests запрещают self marker, percentile и словесное сравнение ребёнка с группой во всех chart/story fixtures.
- Multi-course unit/contract suite проверяет один active group и несколько allowed groups на enrollment; независимые schedule snapshots; course/group Telegram inheritance; merge/split без изменения concrete IDs; chronology provenance; combined review target и split status; synonym counting per group sheet; best-group tie-break; course-scoped progress/strength/notifications; inheritance classroom assignments для выбранных групп события.
- Storybook proof включает `Product/Courses`, Staff catalog/schedules/Telegram, synonym merge/timeline/review, multi-course classroom event, classroom delivery preview/changed-after-send, course-separated progress и соответствующие `Pages/Student`, `Pages/Family`, `Pages/Staff`. Visual snapshots не обновляются до owner review.
