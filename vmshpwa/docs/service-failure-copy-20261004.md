# Server failures and connection messages — 4 October 2026

Owner request after the [production CPU incident](cpu-incident-20261004.md):
explain failures of our service without blaming the user's internet connection.

Evidence controls the message. A gateway 502/503/504 or a failed runtime probe
after a valid same-origin `/service-status` response marks a server episode:
“Сервис временно недоступен. Проблема на нашей стороне.” A fetch failure alone
is ambiguous and gets “Сервер не отвечает” / “Не получили ответ от сервера”.
Only the browser's explicit offline state shows a missing internet connection.
Planned updates retain their own existing explanation and automatic recovery.

Implementation: [`createServiceTransport`](../packages/contracts/src/service-availability.ts)
records cause; [`ServiceAvailabilityBanner` and copy helpers](../packages/app-shell/src/service-availability.tsx)
share titles and copy across [startup](../packages/app-shell/src/runtime-bootstrap.tsx),
[authentication](../packages/app-shell/src/auth-boundary.tsx),
[page states](../packages/app-shell/src/page-layout.tsx) and audience login pages.
Student's [saved-copy notice](../apps/student/src/routes/__root.tsx) uses browser
offline state rather than treating all cache fallbacks as missing internet.
HTTP 5xx login failures are classified separately by
[`classifyAuthLoginError`](../packages/app-shell/src/auth-client.ts). Security validation, expiry,
401/403 handling and write-replay/idempotency policies remain unchanged.

Verified:
[`transport evidence tests`](../packages/contracts/src/service-availability.test.ts),
[`reactive copy tests`](../packages/app-shell/src/service-availability.test.tsx),
[`startup rejection tests`](../packages/app-shell/src/runtime-bootstrap.test.tsx),
[Storybook states](../packages/app-shell/src/service-availability.stories.tsx),
[actual bad-gateway recovery and preserved form/receipt/outbox](../e2e/smooth-redeploy.spec.ts).
The selected gate is `make pwa-check-fast PWA_E2E_MODES="redeploy offline-current"`
(Chromium; copy/classification change, recovery timing and lifecycle unchanged).
Release prepared for owner-authorized push/autodeploy and the guarded
[frontend-only TLF release](../../pwa_tests/reports/service-failure-copy-20261004/deploy-tlf.sh)
with read-only smoke. No backend restart, migration or content mutation.

The first full gate exposed an existing wall-clock mismatch in
[`review_http`](../../pwa_tests/integration/test_review_queue_http_api.py): claims
used the fixed fixture clock, while the real correction domain defaulted to
current UTC. After 13:00 UTC on 4 October the synthetic resubmission violated
monotonic time; extending that timestamp also expired the synthetic lease.
The fixture now passes the same `now=NOW` to the real correction function.
The targeted append-only/stale-reaction/lease scenario passes; production
backend code and behavior are unchanged. The interrupted retry did not reach
frontend suites; the final full gate below passes before deployment.

The real cold-start gateway test also exercises
[`renderBrandingWaiting`](../packages/branding/src/startup.ts), before React or
the main runtime screen mounts. It receives the same cause from the transport
and now explains known server failure (including prolonged recovery) and uses
neutral wording for an unknown cause.
[`branding tests`](../packages/branding/src/startup.test.ts) check translated
text before React. The final [catalog-failure screen](../packages/i18n/src/catalog-failure.ts)
also no longer blames an unconfirmed local connection problem.

Final fast gate `20261004T131843.325401Z` PASS in 329.594 s: Python
2840 / 7 existing SKIP, frontend 1042, Storybook 362, Chromium E2E 9.
Types, formatting, ESLint, CSS lint, Russian/English catalogs and four-app build
pass. Real gateway failure shows our server message at the first screen and
automatically recovers. The form, photograph, outbox and receipt scenarios
pass. The 320 px light/dark images were visually inspected with no overflow.
[Gate and artifacts](../../pwa_tests/reports/service-failure-copy-20261004/README.md).
