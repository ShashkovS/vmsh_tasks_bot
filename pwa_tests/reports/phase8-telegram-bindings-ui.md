# Phase 8: Telegram binding verification and Staff UI

## Scope delivered

- Telegram bindings can be listed and edited without starting polling or loading Google settings.
- Staff discovers valid course/group owners from the API instead of hard-coding identifiers.
- A draft binding is verified by a one-shot Bot API check (`getMe`, `getChat`, `getChatMember`) and stores the canonical chat title and identifier.
- Verification rejects unsupported chat kinds, missing administrator membership and missing channel posting rights.
- Staff can create a draft and explicitly verify, disable or restore it from `/staff/courses`.
- TypeScript requests and responses are checked by strict Zod contracts; mutations use the exact entity ETag.

The verifier deliberately does not prove that a particular forum topic exists. It verifies that a topic binding points to a forum-enabled supergroup; exact topic availability remains a later live-integration check.

## Implementation links

- HTTP routes: `apps/pwa_api/telegram_binding_routes.py`
- One-shot Telegram check: `helpers/pwa/telegram_bindings.py`
- Owner lookup SQL: `db_methods/pwa/telegram_bindings.py`
- Contracts: `vmshpwa/packages/contracts/src/telegram-bindings.ts`
- Authenticated client: `vmshpwa/packages/app-shell/src/telegram-binding-client.ts`
- Staff screen: `vmshpwa/apps/staff/src/telegram-bindings-page.tsx`
- Product component: `vmshpwa/packages/product/src/course-admin.tsx`
- Storybook: `Product/Staff admin--Telegram binding lifecycle`

## Proof

- Backend focused regression: **48 passed** (`test_telegram_binding_verifier.py`, `test_phase8_telegram_bindings.py`, `test_pwa_app.py`, `test_app_factory.py`).
- Contracts and authenticated client: **9 passed**.
- Full frontend unit regression: **69 files, 472 tests passed**.
- Storybook interaction file: **4 passed**, including draft → verified → disabled → draft.
- Strict TypeScript checks passed for contracts, app-shell, product and Staff.
- ESLint and Prettier passed for all touched frontend files.
- Staff production build passed: **3061 modules transformed**.
- Manual Storybook inspection passed at desktop and 390×844 mobile-light sizes. The lifecycle controls and responsive layout were checked; browser console contained no application errors.
- Visual snapshots were not updated.
- No real Bot API mutation was made by this slice; live verification remains opt-in through the dedicated test bot/channel configuration.

## Staff audit follow-up — 2026-08-02

The searchable Staff timeline now understands `telegram_binding` and renders the
exact destination/status changes with Russian field and action labels. The accepted
audit story includes a verified course destination; focused Storybook interaction and
a11y remain **2/2 passed**. No visual baseline was changed.
