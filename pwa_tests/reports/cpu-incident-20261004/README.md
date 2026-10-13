# Production CPU correction — 4 October 2026

[Incident and implementation](../../../vmshpwa/docs/cpu-incident-20261004.md).

`rehearse.py` compares the actual proposed SQL against the deployed SQL on one
read-only production snapshot, with a two-second deadline per statement. Its
[15-case receipt](rehearsal.json) contains timings, row counts, VM-step counts and
the candidate query plan, without student identities or educational content.
Every row/column is identical; 103–277 ms becomes 4–28 ms under CPU saturation.

`probe-runtime.py` samples CPU, read/write queues, HTTP rate and WebSockets from
the host's existing public local metrics. It never authenticates or writes data.

`make pwa-check-fast PWA_E2E_MODES="content submissions"` passed in 469 seconds:
2840 Python / 7 existing skips, 1032 frontend, 356 Storybook, 5 Chromium cases.
All dependency/format/types/lint/i18n checks passed, source digest unchanged.
[Gate receipt](gate.json), [Chromium receipt](e2e.json).

The initial focused command passed 181 checks with one HTTP fixture blocked by
sandbox loopback restrictions; the full gate passed that fixture with the
authorized isolated server.

`bdfcf9a2` is deployed on VMSh by the webhook and TLF Prep manually. Both portals
pass 25 public read-only HTTP checks. [VMSh proof](production-vmsh.json),
[TLF proof](production-tlf.json), [TLF deploy log](deploy-tlf.log),
[VMSh HTTP smoke](http-vmsh.log).

VMSh [before](runtime-before.json): CPU 98.68–99.34%, read queue 178–361,
write queue zero, completed HTTP rate 27–55/s. [After](runtime-after.json): CPU
24.13% at an initial 18/s burst, then 3.52–8.01%; queues zero.
[A later sample](runtime-after-steady.json): CPU 6.70–8.47%, queues zero,
21 WebSockets connected. These ordinary-traffic samples have different request
rates; the same-snapshot SQL rehearsal supplies the equal-input comparison.

Frontend/dependencies/schema are unchanged. TLF restarts only PWA; NATS and Zoom
PIDs are preserved. Before/after backup integrity is `ok`, with 1593 Zoom
receipts. No production content/publication/grade mutation was performed.
