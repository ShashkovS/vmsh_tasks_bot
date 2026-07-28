# Phase 3G — authenticated Student offline reading

Дата: 2026-07-28

Revisions: `50cd541`, `d4b0b9b`, `89cefb7`, `bb6c6ef`, `d822e2e`

## Проверяемый результат

- после успешного входа Student сохраняет в Dexie только проверенный Zod
  auth snapshot: audience, public principal, owner ID и срок сессии; cookie,
  Telegram-токен, session ID и другие секреты в IndexedDB не попадают;
- при настоящем сетевом отказе и ещё действующем snapshot кабинет открывается
  в состоянии `offline-unverified`, но только для прежнего owner namespace;
- `home`, course access/enrollment, lesson archive/detail, canonical problem
  list и опубликованное condition сохраняются как отдельные валидированные
  документы с `ownerId`, resource identity, revision/version, `fetchedAt` и
  `expiresAt`;
- повреждённая запись удаляется, просроченная остаётся читаемой только как явно
  помеченная stale copy, а authoritative `401`, `403` и protocol error никогда
  не заменяются локальным ответом;
- общий бюджет document cache равен 10 MiB и 500 записям на owner; вытеснение
  детерминированно удаляет самые старые записи;
- раскрытая после успешного audit POST подсказка повторно открывается без сети.
  Нераскрытый материал не может быть раскрыт офлайн;
- смена публикации безопасна: старый cached reveal разрешено использовать
  только когда текущая problem projection имеет состояние `revealed`. Состояние
  `available` новой публикации не доверяет старой локальной копии;
- подтверждённый logout, истечение snapshot, authoritative отказ сессии и смена
  аккаунта атомарно очищают documents/outbox/authentication прежнего owner;
- offline UI сообщает время последней сохранённой копии и отдельно отмечает
  истёкший срок свежести.

Публичный runtime config сохраняется отдельно в audience-scoped localStorage,
потому что он нужен до создания Dexie provider. В кэш попадает только уже
проверенный runtime без auth state; ответ другого audience и server `5xx` не
используют fallback.

## Реализация

- durable auth boundary:
  `vmshpwa/packages/offline/src/authentication-store.ts`,
  `vmshpwa/packages/app-shell/src/auth-context.tsx`;
- versioned document cache:
  `vmshpwa/packages/offline/src/document-cache.ts`;
- Student read-through transports и reveal policy:
  `vmshpwa/apps/student/src/offline-student-data.ts`;
- production composition:
  `student-home-page.tsx`, `student-tasks-page.tsx`,
  `student-task-detail-page.tsx`, `content-page.tsx` и
  `routes/__root.tsx`;
- safe runtime bootstrap:
  `vmshpwa/packages/app-shell/src/runtime-bootstrap.tsx`;
- account-scoped published-content query key:
  `vmshpwa/packages/contracts/src/content-api.ts` и
  `vmshpwa/packages/content/src/content-client.ts`;
- condition/hint matching fix and DB invariant:
  `db_methods/pwa/content.py` и
  `migrations/0045.pwa_material_reveal_matches.sql`;
- Storybook interaction:
  `Product/Reading--offline-last-copy`;
- production browser proof:
  `vmshpwa/e2e/content-publication.spec.ts`.

KaTeX/fonts и application shell входят в настоящий `injectManifest` precache.
Изображения остаются в отдельном audience-owned Workbox CacheFirst cache с
лимитом 80 объектов и сроком 14 дней; они не расходуют 10 MiB document budget.

## Инварианты и отрицательные сценарии

- cache key кодируется как однозначный JSON tuple из owner, kind и resource
  parts, поэтому `:` или `/` в public ID не создают collision;
- чтение всегда повторно валидирует envelope и payload тем же Zod contract;
- другой owner и другой resource не видят запись, даже если знают её внешние
  идентификаторы;
- произвольная ошибка приложения не считается отсутствием сети;
- unaudited reveal при сетевой ошибке завершается ошибкой, а не чтением cache;
- cached reveal предыдущей публикации не открывает новую публикацию;
- второй Student после server logout первого и нового реального login не видит
  condition или hint первого Student при отключённом API;
- Family published-content query также получил account-scoped key, поэтому
  shared TanStack Query cache не смешивает семейные аккаунты.

## Результаты проверок

- `make pwa-test`: **34 TypeScript файла / 283 PASS** и полный Python PWA
  regression **1101 PASS, 3 skip**;
- targeted offline/runtime/contracts: **3 файла / 26 PASS**;
- migration/repository targeted up/down/up: **5 PASS**;
- `make pwa-lint`, `make pwa-typecheck`: PASS;
- `make pwa-storybook-test`: **36 файлов / 182 PASS**, a11y gate включён;
- `make pwa-e2e-content`: production builds и **3 PASS** в Chromium, Firefox и
  WebKit на настоящих aiohttp/SQLite, без MSW;
- E2E выполняет Staff upload → compile → match → publish condition/hint →
  Student audited reveal → полный reload с недоступным Student API → чтение
  condition и hint из Dexie → возврат online → replace/rollback → login второго
  Student → повторный offline probe без утечки первого owner;
- Student `injectManifest`: **96 precache entries / 2289.04 KiB**; Family:
  **91 / 2204.35 KiB**;
- canonical schema inventory обновлён после `0045`; `git diff --check`: PASS.

Playwright context-wide offline не используется для самого navigation:
Firefox и WebKit отклоняют его до того, как уже активный Service Worker может
ответить shell. Вместо этого E2E после полной перезагрузки заставляет все
Student API `fetch` завершаться нативным `TypeError`, не создавая mock response.
Установка, scope и владение precache Service Worker проверяются отдельным
production `runtime-isolation.spec.ts`.

## Намеренно открыто

- performance proof длинного математического документа и большого числа KaTeX
  формул остаётся последним инженерным gate Phase 3;
- visual snapshots не обновлялись; owner visual approval остаётся отдельным;
- браузер может удалить IndexedDB по своей storage policy, особенно Safari без
  установленного PWA. В cache нет единственной копии критичных данных;
- draft/outbox письменных и тестовых сдач входят в этапы 4–5, а не в этот read
  slice;
- Family offline reading будет подключено в семейном вертикальном срезе; здесь
  изменена только безопасная query-key граница Family.

Phase 3G закрывает authenticated Dexie, cold-reload reading и межаккаунтную
изоляцию. Весь Phase 3 остаётся открыт до performance и ручного visual gate.
