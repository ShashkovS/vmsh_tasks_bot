# Phase 6U proof: Student and Staff support pages

Date: 2026-07-29

Revision: `892646f` — production Student and Staff routes for private questions,
replies and reload-safe text drafts.

Authoritative plan:
[`vmshpwa/dev/development-plan/10-phase-6-review-and-feedback.md`](../../vmshpwa/dev/development-plan/10-phase-6-review-and-feedback.md).

## Accepted vertical slice

- Student has a private questions inbox, a problem-scoped compose route and a
  chronological thread route. Every live task links to the exact
  `groupLessonId + problemId`; no legacy negative problem ID is used.
- Staff has a scoped inbox with validated `state`, `kind`, `course` and `group`
  URL filters, plus a compact chronological thread/reply route.
- Both audiences call the authenticated support API and use its typed TanStack
  Query hooks. Family receives no write route.
- Unsent text is saved on every edit in the account/audience/instance/target
  `localStorage` namespace. Its idempotency key and client timestamp survive a
  reload; the draft is cleared only after the server confirms the mutation.
- A storage failure is visible in the composer and does not discard the
  in-memory text.
- The task page and Student profile expose the new routes. TanStack Router
  generated split route trees include all Student and Staff question pages.

Implementation and executable specification:

- `vmshpwa/apps/student/src/student-support-pages.tsx`
- `vmshpwa/apps/student/src/routes/questions*.tsx`
- `vmshpwa/apps/staff/src/staff-support-pages.tsx`
- `vmshpwa/apps/staff/src/routes/questions*.tsx`
- `vmshpwa/packages/offline/src/support-draft-react.ts`
- `vmshpwa/packages/offline/src/support-draft-react.test.tsx`
- shared visual/interaction contract:
  `Product/Feedback--private-support-dialogue`

## Executable evidence

- `make pwa-lint`: **PASS** (ESLint and Stylelint).
- `make pwa-typecheck`: **PASS** (route generation, all applications,
  packages and tools).
- `make pwa-test`: **420 frontend tests passed** and **1297 Python tests
  passed / 3 intentional skips**. The first sandboxed run could not bind
  loopback sockets; the authoritative rerun with local aiohttp access passed.
- `make pwa-storybook-test`: **41 files / 199 tests passed** with the a11y gate.
- `make pwa-build`: **PASS** for Student, Family and Staff production builds;
  Student and Family produced `injectManifest` service workers.
- Focused React/store specification: **8 tests passed** across the persistent
  store and hook.
- Prettier and `git diff --check`: **PASS**.

## Still open

- support image attachments and their media-proxy flow;
- a discoverable general-lesson question entry point after the current lesson
  selector is connected to real course context;
- production-build Playwright coverage for Student create/reload/reply and
  Staff scoped reply, including a forbidden teacher scope;
- owner visual review of the real application routes; snapshots were not
  updated;
- Telegram continuation of the same logical support thread.

This proof accepts the text-only application flow. It does not close Phase 6.
