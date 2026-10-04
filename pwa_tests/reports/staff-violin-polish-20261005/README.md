# Staff violin polish — 5 October 2026

Implementation/decision: [lesson statistics](../../../vmshpwa/docs/lesson-statistics.md#staff-violin-polish-2026-10-05).

The owner explicitly authorized deployment to both production portals after the
existing journal performance failure was disclosed. This frontend-only release
uses VMSh's protected webhook and the guarded TLF static release procedure; no
backend, dependency, migration or service configuration changes are included.

`verification.json` preserves the fast gate exit 1: 2840 Python (7 skips),
1048 frontend, 362 Storybook pass; unchanged LargeClassroom p95 60.1 ms against
50 ms, isolated 59.7 ms. The final statistics E2E assertion covers constant
samples via the quartile rectangle; the normal lock-aware runner passes all
3 Chromium cases (`e2e.json`). No performance thresholds or golden snapshots
were weakened. Dense graphs and page screenshots were reviewed in light/dark
at 320/390/1280 CSS px and 200% zoom. `preview-proof.json` and two previews
retain the dense graph evidence; the existing 200% header overlap is recorded
in the decision document.

Production release is in progress. Pre/post release checks and public HTTP
reports will be recorded here before this entry is marked complete.
