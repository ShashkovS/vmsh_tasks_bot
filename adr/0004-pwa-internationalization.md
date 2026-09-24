# ADR 0004: PWA internationalization (Russian source, English translation)

- Status: accepted; Phase P0 (infrastructure) implemented
- Date: 2026-09-18
- Scope: Student, Family and Staff PWAs, Landing, and the PWA HTTP/WebSocket
  and Web Push backend. The Telegram bot stays Russian.

## Context

Every user-visible string of the PWAs was hard-coded Russian: about 3 800
lines across 200 frontend files, about 530 distinct backend error messages
rendered verbatim by the frontend, and server-built Web Push texts. The owner
asked for a complete English interface chosen per account in the personal
cabinet, with Russian as the default, delivered in deployable phases and
without a noticeable slowdown. The earlier plan deferred i18n to "v2"
(`vmshpwa/dev/development-plan/02-data-model.md`).

The stack constrains the tooling: Vite 8 with Rolldown, `@vitejs/plugin-react`
v6 (no built-in Babel), Vitest 4, Storybook 10, React 19, TanStack Router with
route code splitting, Student/Family service-worker precache and a Staff SPA
without a service worker.

## Decision

### Frontend: Lingui 6 with Russian source text in code

- Product copy stays Russian in the source and is wrapped in Lingui macros
  (`<Trans>`, `t`, `msg`, `plural`). The Russian text with an optional context
  is the message key; no hand-named keys.
- Macros are expanded by `@rolldown/plugin-babel` with
  `linguiTransformerBabelPreset`, whose code filter sends only files importing
  a Lingui macro through Babel. `.po` catalogs are compiled at build time by
  `@lingui/vite-plugin`; the browser never parses ICU messages.
- Production builds keep only message IDs in code (`descriptorFields: auto`).
  Each app merges the catalogs of its `@vmsh/*` packages into one chunk per
  locale (`apps/<app>/src/i18n/catalog-<locale>.ts`). The default Russian chunk
  is preloaded from `index.html`; the service worker precaches both locales.
- A build guard (`vite-i18n.ts`) fails a production build if any message ID in
  the code is missing from the app's catalogs, so a forgotten extraction or an
  unmerged package catalog can never render a hash.
- The catalog is activated before the first render (`bootstrapLocale`), and
  `LocaleProvider` wraps every app outside the runtime bootstrap, update and
  offline fallback screens. A failed Russian catalog shows a static bilingual
  reload screen.
- `@vmsh/i18n` owns locales, the device cookie, catalog activation, the
  provider and cached `Intl` formatters (English formats as `en-US`, the
  owner's decision of 2026-09-19). It sits at the bottom of the package graph.
- The brand «ВМШ 179» is written «VMSh 179» in English
  (`vmshpwa/docs/i18n-glossary.md`).

### Language preference

- The account preference is authoritative (`auth_accounts.locale`, Phase P1).
- The cookie `vmsh-locale` (`Path=/`, `SameSite=Lax`, one year, not HttpOnly)
  stores the language last chosen on the device. Screens before sign-in and the
  backend (HTTP and the WebSocket handshake) read it, so the ~40 independent
  `fetch` call sites need no header. It is a convenience, not user data.
- Russian is the default for every account and device; the browser language is
  not consulted.
- Choosing a language saves it to the account (`PUT /{audience}/api/v1/auth/locale`),
  writes the cookie and reloads the page (P1 amendment, 2026-09-22): code uses
  the global `t` macro, so a reload guarantees no stale text in module
  constants, cached formatters or helpers. Sign-in and `/auth/me` sync the
  cookie with the account; another device's change applies on the next load.

### Backend: Russian literals as keys

- `helpers/pwa/i18n.py` translates Russian literals through
  `helpers/pwa/locales/en.po`, read once with Babel's `read_po`; a missing
  translation falls back to Russian. `pwa_error_middleware` sets the request
  language from the cookie and translates every `PwaApiError.message`, so most
  routes keep their literals unchanged. Varying values move to `params`.
- Texts built for another recipient (Web Push) use the recipient's account
  language explicitly.
- `vmshpwa/scripts/backend_i18n.py` extracts `N_()`, `_()` and
  `PwaApiError(message=...)` literals and checks the catalog.

### Phasing and quality gates

- `vmshpwa/i18n-scopes.json` lists translated areas. In those areas ESLint
  (`lingui/no-unlocalized-strings`, Cyrillic only) bans unwrapped Russian, and
  `make pwa-i18n-check` requires English for every owned message. Each phase
  adds its areas; English is visible to everybody from P1, untranslated parts
  remain Russian.
- Unit, Storybook and E2E tests keep rendering Russian, so existing assertions
  stay valid; English gets dedicated tests.

## Consequences

- Developers write Russian as before but inside macros, run
  `make pwa-i18n-extract` and translate the new `msgstr` entries.
- Changing Russian source text creates a new key; the English entry must be
  translated again, which is the desired behavior.
- Production message IDs mean catalogs are mandatory at runtime; the build
  guard and `make pwa-i18n-check` protect this.
- Tests that render components using `<Trans>`/`useLingui` need
  `renderWithI18n` from `@vmsh/test-utils/i18n`.
- Measured P0 overhead: +2.7–3.8 KB brotli initial JS per app and first
  contentful paint within ±12 ms of the baseline
  (`vmshpwa/dev/i18n-performance-report.md`).
- Out of scope: the Telegram bot, lesson content (statements and compiled
  labels such as «Задача N»), news, course/group names, legacy dashboards and
  import/export formats.
