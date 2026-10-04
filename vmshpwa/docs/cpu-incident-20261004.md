# PWA CPU incident — 4 October 2026

Owner reported 100% production CPU after the hint-preview release. Investigation
at 12:12–12:17 UTC identified both VMSh PWA interactive read threads, with more
than 300 waiting reads and ordinary requests delayed by 5–8 seconds. TLF Prep
was idle. Memory and disk wait were not the limiting resources.

The problem-list query in
[`content.py`](../../db_methods/pwa/content.py) materializes the global
`effective_results` / `teacher_result_choices` winner projection for every
Student request. A bounded read-only comparison on a single production snapshot
found the same global scan before `cc60df33`; hint availability is not the cause.

Correction implemented: restrict candidate aggregation to `:student_user_id`
before choosing winners in
[`effective_results.py`](../../db_methods/pwa/effective_results.py), and
materialize the small published-scope / visible-problem / logical-member CTEs
once. No schema, publication, grade or credential changes. The rules remain the
[written-result precedence contract](written-result-precedence.md).

Production SQL rehearsal: original 148–174 ms / 2.45–3.01 million VM steps;
candidate correction 8–10 ms / 150–171 thousand steps; all 17 result rows
identical in both empty-history and recent-student cases. Each probe had a
two-second SQLite progress-handler deadline and used `mode=ro` in one snapshot.

The exact implemented query also passed 15 production comparisons (three
students, five published lessons): every row/column identical; original
103–277 ms, correction 4–28 ms under the ongoing CPU saturation.
[Reproducible bounded probe and report](../../pwa_tests/reports/cpu-incident-20261004/rehearse.py).

Verification: extend the existing entire-grade parity matrix in
[`test_written_result_precedence.py`](../../pwa_tests/integration/test_written_result_precedence.py),
add an actual problem-list query-plan assertion against global result/manual
cell scans, run the focused fast gate, then deploy the backend and compare CPU,
read queues and HTTP behavior under ordinary traffic. Preserve production data
and static assets; follow-up receipts are recorded here after execution.

Fast gate PASS in 469 seconds: 2840 Python / 7 existing SKIP, 1032 frontend,
356 Storybook, 5 Chromium cases (`content submissions`); format/types/lint/i18n
PASS. Source digest unchanged during the gate.
Initial focused invocation passed 181 tests, with one HTTP fixture blocked by
the local sandbox socket permission; the full gate with authorized isolated
loopback servers passed that fixture. No test was skipped or weakened.

Before release (12:25:30–12:25:36 UTC), CPU was 98.68–99.34%, read queue
178–361, write queue zero, completed HTTP rate 27–55/s.
[Runtime sample](../../pwa_tests/reports/cpu-incident-20261004/runtime-before.json).

The 15-case rehearsal median is 143.94 → 5.695 ms; VM steps 3,130,000 →
158,000. Production rollout is the remaining verification step.
