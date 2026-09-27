# P8 — final localization coverage

## Publication decision — 27 September 2026

The owner explicitly authorized committing and pushing the current P8 implementation
for their production verification after the bounded flaky-test repairs passed
36/36 checks with retries disabled. This supersedes earlier no-push instructions.
The complete E2E gate remains pending; performance optimization remains deferred.
Earlier verification entries below describe the state at the time of each run.

## Bounded flaky-test verification — 27 September 2026

The three pending test repairs are now verified: logout opens a fresh protected
tab with the same cookies/storage instead of racing an automatic reload;
archive history selects the card's h4 rather than the asynchronously loaded
statement's h2; Whiteboard cancellation holds the real export-data request
before images can be cached. No tests were disabled or assertions weakened.

A temporary Make target used the existing E2E runner's cross-process lock,
sanitized environment, build and isolated database reset. Only these scenarios
ran twice in Chromium, WebKit and Firefox, with `--retries 0`: **36/36 passed
in 3.9 minutes**, with no retries. Focused ESLint and Prettier checks passed.
The complete task took about five minutes, within the owner's ten-minute cap.
No full-suite rerun, commit or push. The full P8 gate remains pending; these
results supersede the earlier "unverified" status for these three repairs.


Source revision: `c0c3df02`; initial worktree clean. Implementation follows
[P8 of the execution plan](24-i18n-execution-plan.md#p8--complete-coverage-remaining-labels-landing-maintenance-and-final-audit).
Implementation: 26–27 September 2026. Final broad verification is blocked by browser failures and extreme host load.
The all-tests-green condition is not met; publication is now explicitly authorized
by the owner as recorded above.

## Implementation inventory

- [Landing](../../apps/landing/src/landing-page.tsx) translates its public copy,
  destination cards and accessible brand labels. [Bootstrap](../../apps/landing/src/main.tsx)
  updates the title and description after loading the device-selected catalog.
  Russian remains the no-cookie default. Manifest branding is unchanged.
- Remaining [Student](../../apps/student/src/pages.tsx) and
  [Family](../../apps/family/src/pages.tsx) compositions, login wrappers and
  profile links are localized. These files mix production routes with story
  compositions; fixture names, problem content and authored comments remain
  data with narrow lint annotations.
- Shared annotation, table selection, zoom controls and
  [StudentProgress](../../packages/product/src/student-progress.tsx) are
  translated. Progress uses ICU plurals rather than Russian modulo rules.
- [LiveMarkingQueue](../../packages/offline/src/live-marking-outbox.ts) emits
  stable local error codes; the [Staff page](../../apps/staff/src/live-marking-page.tsx)
  translates them. Unknown server error messages remain intact. No localization
  dependency was added to the storage package.
- Backend live-marking and legacy-print error registries are extractable using
  `N_()`. The deleted-account analytics fallback is translated at the response
  boundary. Print keys, group codes and export data remain unchanged.
- [Written notice projection](../../../helpers/pwa/written_notice_i18n.py)
  translates exact transfer/copy templates only for system-authored system
  events in Student/Family thread responses. It copies the response and keeps
  stored text, problem labels and all authored/unknown messages unchanged.
- [nginx](../../deploy/nginx/vmshpwa.conf.template) and the
  [E2E gateway](../../scripts/e2e_gateway.py) return identical bilingual 503
  copy. Status, `service_updating`, retry/cache headers and recovery behavior
  remain unchanged. The transport's unconfirmed-write fallback is bilingual;
  the existing catalog-failure screen already provides bilingual reload help.
- [Scopes](../../i18n-scopes.json) now cover every production app/package TS/TSX
  source and the full PWA backend extraction roots. ESLint excludes tests,
  stories, the test-utils package and two explicitly named content/course
  fixture modules. Generated routes remain excluded by the existing global
  rule. UI Select imports use `UiSelect` to avoid Lingui's macro-name exemption.

## Retained Russian text audit

Russian macro bodies and PO keys are the source language. Remaining raw strings
fall into these boundaries:

- Course/group/student/room names, problem numbers/titles, authored lesson and
  news content, comments and fixture data. Existing Staff fixture content was
  removed from translation macros; UI dates and durations were translated.
- Language choices retain endonyms (`Русский`, `English`) from
  [locale.ts](../../packages/i18n/src/locale.ts).
- Fixed XLSX sheet names (`Задачи`, `Старые`), group-code syntax, regexes and
  normalization of Russian names. These are protocol/data semantics.
- `studentLabel: "Перенесено преподавателем"` remains a legacy wire literal.
  The production frontend has no reader of this field; the reassignment UI
  already uses translated labels derived from stable event semantics.
- Organizer schema diagnostics are internal validation details. The organizer
  page catches non-API failures with its own localized user message.
- System-generated transfer notices are translated by proven author/event
  kind and known templates, not by globally replacing matching user text.
- Telegram message bodies, compiler/model input, bootstrap account names,
  stored device descriptions and arbitrary historical audit values remain
  content. They are not PWA interface translation targets.
- Explicitly bilingual maintenance/catalog-failure/transport fallback text
  remains usable before catalogs or the backend can load.

## Feedback provenance decision

The P3 trace still holds: `models/pwa/submissions.py` marks built-in evaluation
defaults; `db_methods/pwa/submissions.py` persists that marker in new receipts
and proves history using immutable revision configuration and evaluation
fingerprints; `apps/pwa_api/submission_routes.py` translates initial, retry,
history and recheck projections. Custom text equal to a default is preserved.
The tests in `pwa_tests/integration/test_content_http_api.py` cover this boundary.

Historical feedback without sufficient provenance cannot safely be classified
as built-in. The execution plan requires an explicit owner decision for this
subset. A question accepting source-language preservation has been sent;
until answered, final acceptance of that subset remains open.

## Verification

- Frontend: **925 tests in 182 files passed** (including actual checker-negative
  fixtures and English plural counts 1/2/5/11/21).
- Backend: **2096 passed, 6 skipped** in the full PWA Python suite.
- Storybook: **316 tests in 65 files passed**. The final audit fixed one remaining
  module-scope translated fixture getter that ran before catalog activation.
- Full lint, typecheck, frontend/backend catalog checks and `git diff --check`
  passed. Changed files are formatted; repository-wide `format:check` reports
  **31 unchanged files** outside P8.
- English Landing screenshots inspected at 1280 px and 390 px: no clipped text
  or controls. The E2E test records both sizes in each browser.
- `make pwa-e2e-i18n`: **36 passed**, all three browsers, including catalog
  HTTP 503 and recovery with the bilingual Reload button.
- WebKit recovery exposed [bug 270357](https://bugs.webkit.org/show_bug.cgi?id=270357):
  failed preloads survive ordinary reloads. [Build wiring](../../vite-i18n.ts)
  now loads the side-effect-free default catalog through a parallel module script,
  retaining the bootstrap language choice. The [bundle reporter](../../scripts/bundle-report.mjs)
  counts this script in initial bytes; there is no accounting rebaseline.
- Focused oral/live-marking regression: **15 passed**, all three browsers.
- Focused smooth-redeploy regression: **15 passed**, all three browsers. The
  photograph assertion opens the durable task route after the confirmed receipt;
  a safe post-update reload may collapse the worksheet’s inline answer form.
- The broad browser regression has not passed. It exposed stale import
  receipt/lesson-heading expectations, date-dependent age assertions, shared
  lesson/lease state and the previously recorded news offline fixture. Test
  repairs use current API values and the existing offline-device contract;
  production authentication and persistence behavior are unchanged.
- The statistics response contract now reuses the course/group lifecycle schemas:
  a newly created draft course no longer breaks the whole statistics page. A
  regression test covers draft courses/groups next to the selected active course.
- The full E2E runner keeps its cross-process lock and now seeds separate phases
  for figure-layout and statistics-recalculation, whose destructive fixture changes
  previously affected content/live-marking scenarios in later browsers. Runner
  tests verify the build order and database reset boundary (**9 passed**).

Performance optimization
remains explicitly deferred by the owner. The cumulative P0 performance budget
is not waived, rebased or declared passed by this phase.

## Final performance measurement

Initial JS includes every eager module script (entry and Russian catalog) and
modulepreload dependency, Brotli quality 11. The catalog stays in the initial
budget after the WebKit recovery fix. Historical P0 is a cumulative reference,
not a paired estimate of translation cost: other product changes and many tests
have been added since P0.

| App     | P0 initial JS | P8 initial JS | Cumulative delta | P8 total JS | RU / EN catalogs |
| ------- | ------------: | ------------: | ---------------: | ----------: | ---------------: |
| Student |      368.7 KB |      391.6 KB |         +22.9 KB |    445.0 KB |   21.6 / 18.3 KB |
| Family  |      336.1 KB |      362.0 KB |         +25.9 KB |    397.4 KB |   18.8 / 15.7 KB |
| Staff   |      402.6 KB |      467.8 KB |         +65.2 KB |    804.2 KB |   40.8 / 35.2 KB |
| Landing |       63.2 KB |       64.2 KB |          +1.0 KB |     64.6 KB |     0.5 / 0.4 KB |

The strict +10 KB cumulative initial-JS budget still fails for Student, Family
and Staff. The owner has deferred catalog-loading optimization; this phase does
not waive the gate or switch to message IDs. FCP and isolated tool timings remain unmeasured: host load made a valid
comparison impossible. A frozen-lockfile P7 snapshot was prepared separately,
but no timing from this overloaded host is presented as performance evidence.

## Remaining verification blocker — 27 September 2026

The last completed broad main stage reported **342 passed, 18 skipped, 8 flaky,
1 failed**. Its only failure was the Firefox photograph assertion described
above; after the assertion repair, the focused redeploy suite passed **15/15**.
The final aggregate rerun was then interrupted in WebKit after repeated timeouts
in the Staff English journey and live-marking confirmation. The Staff failures
occurred at different navigations, including the very first page load before
translation assertions. System load averages rose from 117 to 156 during the
run and to 269 after stopping it. This is a verification blocker, not evidence
that the failed assertions can be waived. No timeout limits were increased and
no failed test was disabled. Only this run's isolated backend/gateway were stopped.

The runner had not reached its separately seeded figure-layout, statistics and
visual phases. Therefore the complete `make pwa-e2e` gate remains pending,
including those phases. Earlier focused passes do not replace this requirement.
The 18 skips above are existing deliberate non-Chromium shared-fixture skips.
Generated review-queue documentation screenshots were restored to the clean
starting revision; no visual baseline was accepted blindly.

Next: run `make pwa-e2e` on an otherwise available host; inspect any visual
failures; measure P7/P8 builds, unit duration and nine-run cold/warm FCP with the
standard scripts; update this report and both status files; commit locally only
after the tests pass. Do not push. The owner's historical-feedback decision
and the explicitly deferred cumulative performance gate remain separate open
acceptance items.


Verification resumed on 27 September after the owner removed machine load
(initial load average 3.89). A fresh `make pwa-e2e` runs the complete isolated
main, figure-layout, statistics and visual phases. Results pending.


27 September rerun found a reproducible Firefox offline-write failure: an
existing service recovery loop held a new offline answer in `sending`.
`packages/contracts/src/service-availability.ts` now rejects offline writes
before waiting for recovery, returning control to the durable outbox. A
regression test reproduced the hang before the fix and passes afterward;
full browser verification is being repeated.

The next broad main run completed with 350 passed, 18 skipped and one flaky
Firefox session-revocation test. `failOnFlakyTests: true` correctly kept the
gate red. Its page-local WebSocket probe lost history after the auth redirect
reloaded the page. The revocation interval now retains probe evidence in the
Playwright process, while login/reconnect scenarios still inspect their current
document. No-reconnect and socket-close assertions remain unchanged in meaning.
The final scoped probe is being verified before another broad run.

The strict aggregate exposed a second offline race in `StudentTestAnswer`: the
chat bubble used the freshly enqueued item’s `queued` status while `sendState`
already said `sending`. It advertised a retryable queue before delivery settled.
The bubble, status copy and retry button now share the in-flight state. The
submission E2E holds the first real POST and asserts sending, no queued label
and no retry button before releasing it; then it tests offline/reload/retry.


## Verification stopped after owner cost feedback — 27 September

No tests remain running. Repeated full runs were an inefficient strategy. The
latest completed main stage reported 348 passed, 18 skipped, 3 flaky; the strict
`failOnFlakyTests` gate failed. Auth logout navigation, archive heading scope
and Whiteboard cancellation test repairs made afterward remain unverified.
Offline transport/UI fixes passed the focused 9-test submission suite; the
revocation probe passed all 75 runtime tests. No commit or push was made.
Do not restart broad tests automatically; agree a bounded verification scope
with the owner first. Final figure/statistics/visual gates and timing measurements
remain pending.
