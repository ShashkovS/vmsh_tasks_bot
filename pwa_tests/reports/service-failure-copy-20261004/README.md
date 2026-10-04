# Server failure messages — 4 October 2026

Decision and implementation: [service-failure-copy](../../../vmshpwa/docs/service-failure-copy-20261004.md).

`make pwa-check-fast PWA_E2E_MODES="redeploy offline-current"` verifies the
copy/classification change in Chromium, including a real bad gateway, a
60-second update, preserved open form, receipt retry, photograph/outbox and
cold offline current lessons. The 320 px server-failure views are captured in
light and dark themes and inspected before release.

The first gate stopped on the existing review fixture's mixed fixed/real
clock after 13:00 UTC. `first-gate-failed.json` records that failure. The real
correction function now receives the fixture clock, consistent with claims;
`fixture-clock-test.log` proves the targeted stale-review/active-lease scenario.
The intermediate retry was interrupted to correct that clock before running
the frontend; its incomplete summary is not a passing gate.

The final full gate `20261004T131843.325401Z` passes in 329.594 seconds:
2840 Python / 7 existing skips, 1042 frontend, 362 Storybook and 9 Chromium E2E;
all static/catalog/build checks pass. `gate.json`, `e2e.json` and `e2e.log`
record the complete successful gate. The 320 px light/dark images are inspected.
`story-copy-gate-failed.json` records stale login assertions updated for the
new text. `pre-brand-gate-failed.json` found the separate pre-React startup
screen; that component is now covered and the real cold-start case passes.
Production evidence is pending. The owner-authorized
release uses VMSh autodeploy and `deploy-tlf.sh` for prep. The latter guards
unchanged backend/dependencies/migrations, builds and verifies production
static bundles before atomic activation, retains old tab assets, and requires
unchanged PWA/Zoom/NATS PIDs. No service stop or database write is part of this
frontend release. Backups and read-only HTTP/provenance probes are retained.
