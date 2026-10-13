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

`0d2d88e3127e1e0937c3043346d3a96c3160bd89` is deployed on both portals:

- VMSh protected webhook: `0d2d88e3127e-20261004223309`.
- Manual TLF: `tlfprep-20261005-violin-polish-0d2d88e3127e`.

Both pass 25 public read-only HTTP checks. `production-vmsh.json` and
`production-tlf.json` confirm all four production build provenances, exact source
hashes and unchanged service PIDs. `public-release.json` verifies all four
provenances through HTTPS and exact SHA256 of the publicly served graph chunks;
`bundle-*.json` confirms integer ticks and two 0.75 Staff callers in those chunks.
`source-proof.json` ties both hosts to the committed graph sources while retaining
the failed gate status and the subsequent E2E assertion correction.

`deploy-vmsh.log` records frontend=true/backend=false/migrations=false.
`deploy-tlf.sh` guards the exact old checkout and unchanged backend/dependencies,
builds in an isolated archived source tree and verifies immutable assets before
atomic activation. `deploy-tlf.log` records 25 HTTP checks, unchanged credentials,
unchanged PWA/Zoom/NATS PIDs and before/after integrity `ok` (1595 Zoom receipts).
Previous release assets and rollback targets are retained. No service restart or
schema/data modification is part of this release. The journal performance failure
and existing 200% page-header overlap remain separately tracked follow-ups.
