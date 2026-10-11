# Portal rollout and GlitchTip switch — 2026-10-11

The owner explicitly requested: commit/push the current verified changes to both
production portals first, then switch DSNs and complete CSP/sourcemap wiring.

## Stage 1, in progress

Base revision: `3af9ffb0`. All 23 product file hashes match the
[quota validation receipt](../../../pwa_tests/reports/sentry-quota-20261011/validation.json).
43 focused Python, 1088 frontend, 364 Storybook, four builds and 12 Chromium checks
passed. Six existing Python failures require missing private `_external_pipelines`
inputs; the full gate is not green. No product source changed after verification.

Publish the reviewed commit to `origin/vmshpwa`, run the existing VMSH deployment
and a separate TLF release, rehearse migration 0117 on a copy, take verified
backups, stop database writers for migration, then verify runtime/static/admission.
Keep existing Sentry DSNs during this stage. Preserve untracked server data,
credentials, existing immutable assets and shared NATS.

## Stage 2, pending

Use the separate frontend/backend projects from [provisioning](README.md):
VMSH 1/2 and TLF 3/4. Update canonical server configuration, persistent production
build configuration and CSP; generate private sourcemaps and upload them with the
exact release ID. Confirm a production SDK event and readable original location
in each correct organization. Keep source maps out of public static releases.

SMTP relay details were requested from the owner. Mail transport can be configured
independently; DSN/CSP/sourcemap work does not depend on that reply.
