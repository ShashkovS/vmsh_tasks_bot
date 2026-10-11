# Portal rollout and GlitchTip switch — 2026-10-11

The owner explicitly requested: commit/push the current verified changes to both
production portals first, then switch DSNs and complete CSP/sourcemap wiring.

## Stage 1, complete

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

Commit `e0324272d535a146898a1fb8cd80b1ad48baa9df` pushed to `origin/vmshpwa`.
VMSH release `e0324272d535-20261011084902`; TLF release
`tlfprep-20261011-sentry-noise-e0324272d535`. Migration 0117, verified before/after
backups and 25 HTTP smoke checks on each portal PASS; maintenance removed.
TLF existing product rows/credentials and shared NATS preserved.

## Stage 2, complete

Use the separate frontend/backend projects from [provisioning](README.md):
VMSH 1/2 and TLF 3/4. Update canonical server configuration, persistent production
build configuration and CSP; generate private sourcemaps and upload them with the
exact release ID. Confirm a production SDK event and readable original location
in each correct organization. Keep source maps out of public static releases.

The owner rejected email and explicitly requested Telegram notifications.
The existing VMSH operator group was selected. The infrastructure webhook
adapter sends bounded, metadata-only messages; portal business APIs stay intact.

[production_frontend_build.py](../../../vmshpwa/scripts/production_frontend_build.py)
consumes a private, explicitly staged portal configuration and preserves all
other canonical settings with a 0600 backup. Each organization's upload token
belongs to its own non-login member, with release permissions only. Subsequent
builds prefer canonical frontend DSN over the older installed shell fallback.
[Vite production guard](../../../vmshpwa/vite-production-guard.ts) generates hidden
maps; the builder uploads release artifacts without injecting or changing hashed
JS/SW bytes, confirms stored artifacts and removes maps before public packaging.
Frontend sessions/client reports/traces and backend GlitchTip traces are disabled;
existing filtering, privacy and durable admission budgets remain enabled.

[Stage 2 verification receipt](../../../pwa_tests/reports/glitchtip-20261011/validation.json):
static checks, 1088 frontend, 364 Storybook, 12 Chromium and 29 focused Python
PASS. Full Python: 2896 PASS / 8 SKIP / six missing-private-input failures;
the full gate remains not green. Real release artifact upload and original
TypeScript resolution in GlitchTip PASS.

[TLF switch script](deploy-tlf-switch.sh) builds an isolated Git archive, preserves
unrelated canonical settings, backs up databases and switches only after private
map upload and public packaging checks. Schema is unchanged from stage 1.
Telegram adapter/unit are installed. The owner explicitly approved the existing
VMSH operator group and a temporary deploy-agent read/SSH transfer of its bot token
to a root-only file on prep. The valid `@vmsh179bot` profile was already on prep:
only token/chat were copied root-to-root, then the temporary file was removed.
No deploy-agent secret handoff occurred; that temporary builder code was removed.
The earlier automatic approval rejection was resolved by this explicit approval.

Full production uploads stored 402 artifacts per release. Initial confirmation
failed before publication because ASGI header names were lowercase and the client
looked for `Link`, so it read only the first 100 files. Header normalization and
a pagination regression now verify all 402. Eight focused production-build
tests PASS, including the explicit one-time Telegram credential handoff.


## Activated releases and live proof

Source `99552697e6d435d42dfd164ae397ec3a7828415f`:
VMSH `99552697e6d4-20261011094249`;
TLF `tlfprep-20261011-glitchtip-99552697e6d4-093337`.
25 read-only HTTP checks on each portal PASS. Canonical frontend/backend DSNs
now point to projects 1/2 and 3/4; both production build entrypoints retain the
canonical selection for future releases. Existing media allowances and immutable
assets remain. Old ingest CSP origins remain for already-loaded versions;
old tabs need a refresh to adopt the new SDK configuration. Hosted project keys
were not disabled, and historical hosted data remains accessible.

Real browser SDK envelopes went only to GlitchTip, with their exact live releases.
[Browser proof](../../../pwa_tests/reports/glitchtip-20261011/browser-ingestion.json)
and [resolved frontend stacks](../../../pwa_tests/reports/glitchtip-20261011/frontend-original-stacks.json)
confirm `packages/i18n/src/catalog-failure.ts:7` in both organizations. The probe
uses a coordinate inside a mapping span; a first boundary coordinate selected a
neighboring vendor token. No production code/mapping workaround was needed.
[Python SDK events](../../../pwa_tests/reports/glitchtip-20261011/backend-ingestion.json)
and [original Python stacks](../../../pwa_tests/reports/glitchtip-20261011/backend-original-stacks.json)
confirm projects 2/4. These probes use the credential-free history-test config
and the deployed `_init_sentry`, without connecting to business databases.

[Telegram adapter](telegram-webhook.py), [unit](glitchtip-telegram.service) and
[provisioning](provision-telegram.py) are installed/enabled. Four native new-issue
rules, quantity 1 over 15 minutes, feed independent authenticated routes.
Only portal/project, new-group count and fixed GlitchTip issue links reach the
operator group. Delivery is confirmed by Telegram API success and service logs;
durable SQLite digests survive restart, deduplicate and send at most once per
15 minutes/project. Queued arrivals during cooldown remain for the next digest.
Bot/config are 0600 root-only and provided through systemd LoadCredential.
The URL secrets are excluded from nginx access logs; private-IP SSRF protection
remains enabled. No email transport or Telegram polling was added.

Fresh GlitchTip snapshot `20261011T100411Z` includes private Telegram configuration,
transport source/unit and a consistent digest-state copy. Actual restore into a
separate temporary database PASS: 3 users, 2 organizations, 4 projects, 11 events.
Memory observed: app 289 MiB/1 GiB, PostgreSQL 97 MiB/768 MiB. Synthetic events
are marked by deployment-check names/environments; no user payloads were used.

Final SDK hardening disables backend frame locals in addition to PII/client reports
and GlitchTip traces. Eleven focused build/SDK/digest checks PASS. The source-side
budgets remain 100 diagnostics + 900 important frontend events per rolling 32 days
per portal. This limits repeated software noise even on self-hosted storage.
