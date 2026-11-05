# Password wording in Student login — 4 November 2026

The owner requested removing Telegram/token wording from the login form in both
languages and immediately deploying to VMSh and TLF without the full test gate.
Application commit: `eed1c1277d54047328f44535f74f244e97c33949`.

[StudentLoginPage](../../../vmshpwa/apps/student/src/login-page.tsx) now uses
«Пароль» / “Password”, the registration-email hint, and a password-based invalid
credential message. The DOM field is named `password`; the existing Student API
payload remains compatible. Existing unit, Storybook and E2E selectors are updated.

Focused validation passed: `make pwa-i18n-extract`, `make pwa-i18n-check`, the
three existing `apps/student/src/login-page.test.tsx` unit tests, and Prettier on
the five changed TS/TSX files. The full gate and local E2E were not run, as requested.

Both production sites are deployed. Each passed 25 read-only public HTTP
checks and fresh Chromium checks of the Russian and English login form at
390px. The password label, hint, input name/autocomplete and absence of
Telegram/token wording passed; screenshots were visually inspected.
TLF private sourcemap upload was verified before activation.
Each frontend release was built in an isolated archived source tree
with the pinned Node 26 / pnpm 11.15.1 toolchain and unchanged installed
lockfile dependencies. The standard production builder and immutable package
verification run before the atomic static symlink switch. The prior static
release remains available for rollback.

No migrations, service restarts or configuration updates were
part of this frontend release. Unrelated live repairs are preserved. The deploy
script and private build logs remain under
`/web/vmsh_tasks_bot/deploy/releases/login-password-20261104-eed1c1277d54/`.

- [VMSh deployment receipt](vmsh-production.json)
- [VMSh Chromium RU/EN checks](vmsh-browser-proof.json)
- VMSh screenshots: [Russian](vmsh-ru.png), [English](vmsh-en.png)
- [TLF deployment receipt](tlf-production.json)
- [TLF Chromium RU/EN checks](tlf-browser-proof.json)
- TLF screenshots: [Russian](tlf-ru.png), [English](tlf-en.png)
