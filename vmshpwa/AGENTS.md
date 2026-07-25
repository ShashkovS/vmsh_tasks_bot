# vmshpwa workspace instructions

## Scope

This workspace contains frontend adapters and test tooling. The existing Python project remains the only backend. Put domain behavior in existing `models/`/`db_methods/` APIs and expose it through the aiohttp PWA adapter; do not create a second Python service, database schema manager, or duplicate source of truth here.

## Commands and isolation

- Node 26, pnpm 11.15.1 and the committed lockfile are required.
- Agents may start only `make pwa-agent-*` servers. Human targets and ports are reserved for the user.
- Tests use `make pwa-test`, `pwa-storybook-test`, `pwa-e2e` and the isolated e2e profile.
- Never start Telegram polling, load Google credentials, use production credentials, or point tests at human/production SQLite, NATS topics, media, IndexedDB or browser storage.
- Preserve uncommitted and parallel work. Never mass-rewrite files outside the task or discard changes you did not create.

## Architecture

- Applications own routing, audience-specific composition and data fetching.
- `packages/ui` is domain-neutral. `packages/contracts` owns Zod runtime contracts. `packages/offline` owns Dexie/outbox mechanisms. `packages/test-utils` must not enter production bundles.
- All shareable URL state uses TanStack Router search params with runtime validation.
- Server data uses TanStack Query. Do not mirror it into ad-hoc global state.
- Heavy optional features use dynamic imports. CPU-heavy image/content processing uses Vite workers.
- Student and Family PWA code must respect their distinct service-worker scopes and storage namespaces. Staff stays a normal SPA.

## Quality

- Use semantic tokens; raw color utilities and hard-coded product colors are prohibited.
- A shared component change includes relevant stories and visible states. Behavioral components include an interaction test.
- Do not update visual snapshots before inspecting the rendered diff in every affected theme/browser.
- MSW is limited to unit/Storybook. E2E uses real aiohttp. Production must fail closed if prototype/MSW is enabled.
- Do not introduce a production bypass for login or authorization to make prototypes/tests convenient.

## Traceability And Progress

- Non-trivial frontend code comments point to the authoritative design/development decision and name the related component, route, contract, or test; do not duplicate whole requirements in source comments.
- Documentation links back to concrete implementing files and public component names.
- Update `dev/design-system/STATUS.md`, `dev/development-plan/STATUS.md`, and the affected phase file when an increment starts, changes, passes verification, or leaves follow-up work.
