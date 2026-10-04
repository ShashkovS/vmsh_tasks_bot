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
authorized isolated server. Production release results follow after execution.
