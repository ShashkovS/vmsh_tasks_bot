# Browser image upload proof — 8 October 2026

`make pwa-e2e-support`: 15 PASS, Chromium/WebKit/Firefox. Fresh isolated
filesystem backend, literal loopback gateway, no external service access.

[Native worker and reload spec](../../../vmshpwa/e2e/browser-image-upload.spec.ts)
covers synthetic JPEG with EXIF Orientation=6 and a source comment, PNG, WebP,
1/2/10 photographs, no bytes before Send, draft reload, dimensions, metadata
removal and exact SHA-256 of the submitted Blob. Chromium and Firefox used the
native encoder (26 completed organizer intents); WebKit used legacy conversion
after its capability probe failed. Existing Student/Staff dialogue tests passed
in all three browsers.

[Stage timings](native-browser-proof.json) are single local samples, not a
before/after production benchmark. Median per-file preparation: Chromium 30.9 ms,
Firefox 138 ms. Send-to-message-receipt for 10 photos: Chromium 152.5 ms,
Firefox 357 ms. WebKit fallback: 1724 ms. Cross-browser differences do not
establish a speedup factor. Source corpus is synthetic: handwritten-text visual
review and production timing remain separate.

Inspected captures: [Chromium](prepared-10-chromium.png),
[WebKit](prepared-10-webkit.png), [Firefox](prepared-10-firefox.png). The synthetic
EXIF fixture deliberately rotates its landscape text into portrait orientation.

The pinned S3 provider did not enforce SHA-256 or return HEAD checksum;
[redacted live proof](../../../docs/performance/browser-image-upload-s3-proof-20261008.json).
Direct upload remains disabled. Native-browser S3/CORS proof was not run after
the failed prerequisite. Prepared proxy and legacy fallback are covered.

## Final validation

Product implementation is complete, including cached-receipt context checks.
Final relevant release run:
`make pwa-check-release PWA_E2E_MODES="support organizers submissions review figure-layout statistics visual"`.
[Receipt](relevant-release-gate.json), [E2E phases](relevant-e2e-gate.json).
Types/format/lint/i18n, 2867 Python (7 skips), 1054 frontend and 364 Storybook
PASS. Three-browser functional phases: support/native worker 15, organizer 9,
submissions/review 18, figure/layout/export 12, statistics 9 — all PASS.
Visual: Staff 3 PASS; Student 3 FAIL against stale baselines. Inspected differences
in all engines show the additional existing `support-navigation` course fixture
“Другой курс E2E”; no screenshot baseline was overwritten. See
[visual differences](visual-baseline-diffs/chromium-diff.png).
Source digest stayed unchanged during the final run.

The default all-mode release gate is **not green**. Its preceding run
`20261008T094100.161143Z` had 382 passes, 20 skips and 6 failures in existing
navigation cancellation, shared refresh and service-worker handover scenarios.
Failures occur before photo processing; relevant-mode checks above are the
validation for this implementation, not a replacement claim that all-mode passed.
No deployment or production configuration change was performed.
