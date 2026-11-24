# Phase 7 proof: classroom scale rehearsal and v1 print boundary

Date: 2026-08-02

Authoritative plan:
[`vmshpwa/dev/development-plan/11-phase-7-oral-and-classrooms.md`](../../vmshpwa/dev/development-plan/11-phase-7-oral-and-classrooms.md).

## Scale result

The current read-only legacy aggregate contains **1617** Students across the
three mathematical groups. **136** currently have `ONLINE_MODE.SCHOOL`:

- group `н`: 1103 total, 49 in school;
- group `п`: 346 total, 56 in school;
- group `э`: 168 total, 31 in school.

The committed rehearsal is deliberately more pessimistic: one synthetic event
contains **1500 in-person Students** and **15 rooms**. It uses only generated
IDs, names, birthdays and classes and never reads or copies personal data.

`pwa_tests/integration/test_phase7_classroom_scale.py` applies the real
migration chain to an isolated SQLite database, creates the course/group/event,
materializes and confirms a 15-room layout through the normal domain flow,
recalculates a plan, then confirms it. The proof asserts:

- all 1500 eligible Students appear exactly once;
- every assignment is `assigned`, with no `reassigning` row;
- one group never leaks into another room mapping;
- the deterministic least-loaded rule produces 100 Students in every room;
- both recalculation and confirmation stay below a deliberately generous
  5-second regression threshold.

The measured test call was **0.55 seconds** on the current macOS development
machine. This is characterization, not a production latency SLA.

## V1 print boundary

- The confirmed Staff plan is authoritative for Student/Family reads and the
  explicit PWA/Telegram classroom delivery preview and batch.
- V1 intentionally exposes no classroom print/export endpoint. A repository
  search found no classroom print/export route or client action.
- `_external_pipelines/a11_spis_from_xls.py` and the following `a12`–`a14`
  scripts remain the separate legacy print workflow until the second-version
  Staff print section is implemented.
- The operator must still refresh the external workbook and run the legacy
  scripts immediately before physical printing. V1 does not pretend that this
  workbook is a live compatibility projection of the Staff plan.
- Classroom notification delivery never implies that paper has been printed,
  and changing/announcing a plan never launches a print job.
- The future print cutover must read an explicitly chosen confirmed plan
  snapshot, produce its own preview/PDF proof and only then retire the external
  workbook workflow. No temporary v1 export is introduced here.

This boundary follows the owner decision already recorded in
[`product-ux-decisions-2026-07.md`](../../vmshpwa/docs/product-ux-decisions-2026-07.md)
and the external-artifact register; this increment does not modify the legacy
print scripts.

## Executable evidence

- Scale rehearsal: **1 passed**, 0.55-second test call.
- Complete Phase-7 classroom domain/integration selection: **26 passed**.
- Existing production-build browser delivery/reassignment flow:
  **9 passed** in Chromium, Firefox and WebKit, recorded in
  `phase7-classroom-delivery-e2e.md`.
- Targeted Ruff formatting/check: **PASS**.
- `git diff --check`: **PASS** before commit.

The production-size functional gate is accepted. Manual visual acceptance of
the complete classroom planner remains with the product owner.
