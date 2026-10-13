# Phase 2: frontend content/API proof

Дата проверки: 28 июля 2026 года.

Это proof ограниченного frontend vertical slice этапа 2, а не
отметка о завершении всей фазы. Авторитетные требования:
[`06-phase-2-content.md`](../../vmshpwa/dev/development-plan/06-phase-2-content.md)
и серверный proof
[`phase2-content-api.md`](phase2-content-api.md).

## Реализованная граница

- [`content-api.ts`](../../vmshpwa/packages/contracts/src/content-api.ts) задаёт
  strict Zod contracts для revision, positional diagnostics, web/Telegram
  preview, history трёх независимых material slots, publication actions и
  Student/Family published document. Contract включает `sourceId`,
  recoverable compile lease/attempt и не пропускает unknown wire fields.
  Scheduled mutation использует `scheduledLocalTime` + `businessTimezone`, а
  history возвращает абсолютный `scheduledAt` и authoritative IANA timezone;
  timezone браузера не является частью wire.
- Telegram Rich HTML ограничен 32 768 Unicode code points, а не
  UTF-16 code units: граница из 32 768 astral emoji принимается,
  32 769 отклоняется.
- [`content-client.ts`](../../vmshpwa/packages/content/src/content-client.ts) —
  same-origin client с `credentials: include`, fail-closed response parsing, одним
  session refresh после `401`, bounded multipart upload и строгими
  `If-Match`/ETag. Publication и rollback передают серверу
  ожидаемые published и scheduled slots вместе; `409` не
  продолжает мутацию на устаревшем состоянии.
- [`content-page.tsx`](../../vmshpwa/apps/staff/src/content-page.tsx)
  восстанавливает history после reload и даёт три независимых
  workflow: upload → compile с revision ETag → diagnostics → PWA/Telegram
  preview → publish/schedule/cancel/hide/rollback. После optimistic
  conflict выполняется authoritative history refetch.
  Загруженную revision можно продолжить без повторной загрузки, а истёкший
  compile claim — безопасно повторить. Rollback selector показывает только
  предыдущие `ready` revisions; publish/schedule/rollback/hide требуют явного
  confirmation. PWA и Telegram previews стоят рядом на desktop и складываются
  на узком экране.
- Student и Family routes
  ([Student](../../vmshpwa/apps/student/src/routes/tasks.$taskId.tsx),
  [Family](../../vmshpwa/apps/family/src/routes/tasks.$taskId.tsx)) читают
  только published `WebContentDocument` и рендерят его через
  `SemanticMathDocument`. Family child ID всегда задаётся явно;
  loading, unpublished/empty, forbidden, offline и unexpected error имеют
  отдельные fail-closed states.
- При смене published revision Student/Family показывают спокойный update
  marker и продолжают рендерить только новый typed document; внутренние
  compiler/publication данные в audience payload не добавлены.
- Content client не включает prototype/MSW и не добавляет auth
  backdoor. Неудачный refresh передаётся в общий
  `AuthenticationController`, чтобы завершить локальную session.

## Storybook acceptance

[`content-page.stories.tsx`](../../vmshpwa/apps/staff/src/content-page.stories.tsx):

- `pages-staff-content-publication--upload-preview-publish` — файл,
  diagnostics с source position, typed PWA preview, Telegram Rich HTML preview,
  immediate publication и появление hide action;
- `pages-staff-content-publication--optimistic-conflict-refetch` — stale
  publication получает `409`, после чего экран показывает
  актуальную server revision;
- `pages-staff-content-publication--resume-interrupted-revision` — reload
  восстанавливает upload/compile workflow;
- `pages-staff-content-publication--rollback-ready-history` — rollback выбирает
  предыдущую готовую revision и требует confirmation;
- `pages-staff-content-publication--schedule-in-business-timezone` — local wall
  time отправляется с timezone занятия без browser `Date.parse()`;
- `product-content-realtime-replacement-marker--calm-realtime-replacement` —
  audience update marker.

Interaction tests проходят в browser mode с Storybook a11y
`test: error`. Клиент в story детерминированный и внедрённый;
MSW и production API не подменяются.

## Проверки

```text
targeted ESLint, --max-warnings=0
PASS

@vmsh/contracts typecheck
@vmsh/content typecheck
@vmsh/student typecheck
@vmsh/family typecheck
@vmsh/staff typecheck
PASS

vitest unit:
packages/contracts/src/content-api.test.ts
packages/content/src/content-client.test.ts
13 passed

Storybook browser mode + addon-a11y:
upload/resume/two previews/publication/rollback/timezone/conflict/update marker
PASS

production builds:
@vmsh/student build (injectManifest, 92 precache entries)
@vmsh/family build (injectManifest, 91 precache entries)
@vmsh/staff build
PASS

git diff --check -- <frontend increment paths>
PASS
```

Полный repository checkpoint после объединения backend/frontend review fixes:

```text
make pwa-lint             PASS
make pwa-typecheck        PASS
make pwa-test             218 TypeScript + 1028 Python PASS; 3 skip; 1 warning
make pwa-storybook-test   167 PASS
make pwa-build            PASS
make pwa-schema-check     192 product objects PASS
make pwa-e2e-auth         60/60 PASS (Chromium, WebKit, Firefox)
```

## Оставшиеся gates

- Current task URL пока принимает явный public `groupLesson` и
  временный problem ordinal. Список задач и authoritative
  `problemPublicId` read model относятся к этапу 3.
- Asset upload/matching endpoint ещё не дан Staff UI; missing assets
  честно блокируют publication и показывают имена. Live
  S3/TikZ/WebP proof хранится отдельно в
  [`phase2-content-assets-live.md`](phase2-content-assets-live.md).
- HTTP asset resolution/matching, bulk lesson upload, metadata grid/problem
  matching mutation и stored/openable generated PDF не входят в этот frontend
  increment. Safe historical lessons 1–38 backfill tool доказан отдельно;
  owner-reviewed production rehearsal/apply ещё не выполнен.
- Auth production-build Playwright остаётся зелёным 60/60, но отдельная content
  цепочка upload→publish→audience read с настоящим aiohttp/SQLite ещё не
  выполнена. Visual approval тоже открыт; snapshots не обновлялись.
