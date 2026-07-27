# Phase 2: frontend content/API proof

Дата проверки: 27 июля 2026 года.

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
- Student и Family routes
  ([Student](../../vmshpwa/apps/student/src/routes/tasks.$taskId.tsx),
  [Family](../../vmshpwa/apps/family/src/routes/tasks.$taskId.tsx)) читают
  только published `WebContentDocument` и рендерят его через
  `SemanticMathDocument`. Family child ID всегда задаётся явно;
  loading, unpublished/empty, forbidden, offline и unexpected error имеют
  отдельные fail-closed states.
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
  актуальную server revision.

Оба interaction tests проходят в browser mode с Storybook a11y
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
Upload → diagnostics → two previews → publish
Optimistic conflict → authoritative refetch
2 passed, 161 unrelated stories skipped by the focused filter

production builds:
@vmsh/student build (injectManifest, 92 precache entries)
@vmsh/family build (injectManifest, 91 precache entries)
@vmsh/staff build
PASS

git diff --check -- <frontend increment paths>
PASS
```

## Оставшиеся gates

- Current task URL пока принимает явный public `groupLesson` и
  временный problem ordinal. Список задач и authoritative
  `problemPublicId` read model относятся к этапу 3.
- Asset upload/matching endpoint ещё не дан Staff UI; missing assets
  честно блокируют publication и показывают имена. Live
  S3/TikZ/WebP proof хранится отдельно в
  [`phase2-content-assets-live.md`](phase2-content-assets-live.md).
- Bulk lesson upload, metadata grid/problem matching, lesson-window editor,
  PDF control и historical lessons 1–38 backfill не входят в этот
  frontend increment.
- Full production-build Playwright цепочка с настоящим aiohttp и
  SQLite, а также visual approval ещё не выполнены. Snapshots не
  обновлялись.
