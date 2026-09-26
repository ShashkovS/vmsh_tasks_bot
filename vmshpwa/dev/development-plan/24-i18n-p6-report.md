# P6 — Staff content tooling

Source revision: `2233052c`. Initial worktree: clean. State: implementation complete;
functional verification complete (26 September 2026). The strict cumulative P0
performance gate remains open; see the [performance report](../i18n-performance-report.md#p6--26-сентября-2026). No push is authorized.

The requirements are [execution plan P6](24-i18n-execution-plan.md#p6--staff-content-lessons-import-synonyms-figure-layout-and-whiteboard).

| Batch | Inspected/changed implementation                                                                                                                                                                                                                                                                                      | Covered surfaces                                                                                                                                                   | Preserved data                                                                                                                     |
| ----- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------- |
| P6.1  | Staff `content-page`, `problem-review-workflow`, `staff-lessons-page`, `staff-lesson-block-editor`, `staff-worksheet-preview`, `rich-markdown-editor`, `lesson-video-dialog`, `revision-assets-recovery`; Product metadata-grid components and rich/lesson Markdown diagnostic parsers; `problem-metadata-columns.ts` | Upload, revision review, metadata generation and validation, lesson windows, publication confirmation, editor, image recovery, empty/loading/conflict/error states | Markdown/LaTeX, authored titles and feedback, video URLs, Telegram preview HTML, compiler output                                   |
| P6.2  | Staff `problem-import-page`, `bulk-content-upload`, `bulk-content-upload-model`, `problem-synonym-page`; Product `problem-matching`, `synonym-context`; `problem_import_routes.py`, `problem_synonym_routes.py`                                                                                                       | Valid/invalid previews, apply/rollback, synonym merge/separate, plural counts, accessible grid editing and clipboard failures                                      | `Задачи`/`Старые`, column headers, numeric enums, row values, receipt hashes, stable problem IDs                                   |
| P6.3  | Staff `figure-layout-editor`, `whiteboard-export-page`, `whiteboard-export-generator`; `whiteboard_export_routes.py`                                                                                                                                                                                                  | Figure placement/scale, progress, cancellation, conversion and ZIP errors                                                                                          | Existing PNG/ZIP names, rendered statement/solution content, Russian generated statistics sheet, print geometry and archive format |

Additional inspected files require no translation changes: `problem-review-draft.ts`,
`automatic-problem-match-plan.ts`, metadata-grid model/types/clipboard helpers,
`lesson-blocks.tsx`, `content-update-marker.tsx`, shared Content package, and
`whiteboard-zip.worker.ts`. These either contain no UI copy or were translated in
previous phases. Content/lessons/import/synonym/whiteboard route wrappers were
traced to their page components. Figure-layout service exceptions are stable
codes resolved by the existing HTTP error adapter.

Backend diagnostics use a read projection in
[`diagnostic_i18n.py`](../../../helpers/pwa/content/diagnostic_i18n.py), called by
[`content_routes.py`](../../../apps/pwa_api/content_routes.py). It matches known
compiler codes and exact source templates, including old stored revisions. It
copies only `message`/`recovery`; unknown diagnostics, source spans, filenames,
canonical ASTs and persisted values remain unchanged. The registry mirrors
parser/compiler/TikZ diagnostic templates and must be updated when those change.
Metadata-generation errors keep named status parameters; model prompts and
model-authored review notes remain source content. Application-owned warning suffixes/defaults are translated when generated using
the request locale; arbitrary model notes are never matched or rewritten.

Catalog owners: Staff, Product, backend. Source language: Russian. English follows
[`i18n-glossary.md`](../../docs/i18n-glossary.md); no new glossary terms. Scoped
coverage is enforced by [`i18n-scopes.json`](../../i18n-scopes.json).

Verification sources:

- [`test_content_diagnostic_i18n.py`](../../../pwa_tests/test_content_diagnostic_i18n.py): localized messages preserve original diagnostics, source names and authored notes.
- [`test_phase10_problem_import_preview.py`](../../../pwa_tests/integration/test_phase10_problem_import_preview.py): RU/EN valid and invalid preview rows, metadata and hashes are identical except diagnostic messages.
- `problem-metadata-columns.test.ts` checks lazy RU/EN labels and identical TSV values;
  `synonym-context.test.tsx` checks English counts 0, 1, 2, 5, 11 and 21.
- Staff `rich-markdown-editor.test.tsx` and `lesson-video-dialog.test.tsx`: English controls with original Markdown/video content.
- [`i18n.spec.ts`](../../e2e/i18n.spec.ts): English lesson/import/synonym/whiteboard routes.
- Existing RU unit, content API, compiler, import, synonym, lesson-block and whiteboard tests.

Toolchain: Node 26.9.0, pnpm 11.15.1. Dependencies restored with the frozen
lockfile. pnpm 11's automatic dependency recheck is disabled for test commands
with `pnpm_config_verify_deps_before_run=false`; the restored install is used.

## Validation prerequisites

The broad Python run reproduced the seven failures previously recorded in P4/P5.
Maintenance commit `f1bedb07` refreshes the generated schema artifacts to include
the 11 existing lesson-block tables/indexes/triggers (494 total objects; no new
migrations), restores the golden manifest generator's canonical formatting
(parsed JSON and all hashes unchanged), and routes Playwright type imports
through the required network-guard fixture. A `logs/README.md` keeps the documented runtime directory present in clean
checkouts for the external-process register checks; runtime event logs remain ignored.

Storybook prerequisites: content stories now supply a real AuthenticationProvider
with synthetic MSW auth/block responses. Verdict stories use the existing lazy
`writtenReviewVerdict` factory instead of spreading a translated getter before
locale initialization. The metadata grid now places its ARIA grid role on the
table, keeping its live status outside the grid; accessibility assertions remain
enabled.

The content-publication offline fixture now reports `navigator.onLine=false`
while rejecting API fetches, matching the existing service-availability contract
in `packages/contracts/src/service-availability.ts` instead of simulating a
server outage. The print-only solution label in `WorksheetMaterials` restores
the documented `docs/worksheet-print.md` behavior while retaining the prior
removal of its duplicate screen label. Feature E2E suites run with a fresh
isolated database between suites because publication and figure fixtures share
lesson IDs.

## Verification results

- `e2e/i18n.spec.ts`: **27 passed**, Chromium/WebKit/Firefox, including an English
  block-editor validation error and unchanged authored Russian preview text.
- Visual inspection: English Whiteboard controls at 1280 px and 390 px fit without
  clipping; course/group/author data remain Russian. Screenshots are generated by
  the P6 test as `p6-whiteboard-en.png` and `p6-whiteboard-en-narrow.png`.
- Python broad regression: 2085 passed, 6 skipped before the seven known
  prerequisite failures were repaired. Recheck of the five affected test files:
  40 passed, followed by the repaired remaining E2E guard: 1 passed.
- Focused backend P6 diagnostics/import/generation/HTTP boundaries: **16 passed**.
- Full frontend unit suite: **912 passed in 178 files**; paired P5 baseline: **903 passed**.
- Full Storybook: **316 passed in 65 files**, including accessibility and live-marking performance checks.
- Full lint, typecheck and both catalog checks passed. Production builds passed.
- Formatting is checked for changed files. Repository-wide formatting has existing
  **30 unchanged-file failures** outside this phase; those unrelated files are not reformatted.

- Final isolated browser runs: **27 i18n + 6 content-publication + 12
  figure-layout/whiteboard-export/worksheet-print = 45 passed**, all three
  browsers, no retries needed. Whiteboard runs both RU and EN through cancellation,
  asset failure, complete PNG/ZIP generation and dark/mobile rendering; filenames,
  archive members, dimensions and source-content pixels remain covered.
- Student and Family service-worker manifests contain both compiled RU and EN
  catalog chunks.

A final AST audit found the Lingui `Select` name exemption hiding selected-value
fallbacks and bulk-upload option text. Those strings are translated, and the two
UI imports are now aliased `UiSelect` so scoped lint can see inside them. Remaining
Cyrillic candidates are declared plural branches or the documented source/TSV/ZIP
exclusions. `SelectContent` forwards ARIA naming props to the actual listbox; the
new `NamedSelect` controls story verifies the accessible name, selection and
closed-overlay accessibility after its temporary focus guards are released.

## Completion boundary

P6 implementation and functional checks are complete. The incremental measurements
against P5 pass the size/startup/build budgets, but the original cumulative P0
size/startup budget was already exceeded before P6. It remains exceeded and has
not been waived or silently rebased. Keep P6's performance gate open until the
owner decides the comparison policy or authorizes the required optimization.
P7 is now complete; see the [P7 report](24-i18n-p7-report.md). P8 remains queued.
