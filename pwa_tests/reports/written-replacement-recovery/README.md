# Written replacement recovery

Contract: [written-replacement-recovery.md](../../../vmshpwa/docs/written-replacement-recovery.md).

- Unit: 18 passed (`student-written-chat.test.ts`, `written-submission-outbox.test.ts`). Includes all three rejection codes, persisted queue recovery, photographs, concurrent recovery calls, exactly one submission and cleanup only after acknowledgement.
- Production bundles built successfully. Workspace typecheck passed shared packages/Family; Student test-fixture typing was corrected and Student typecheck passed separately.
- Targeted ESLint and formatting checks passed.
- Real-backend E2E (`e2e/test-submission.spec.ts`, Phase 5): Chromium and WebKit passed in the final combined run; Firefox passed in a separate isolated run (3 browser scenarios passed). Scenario covers offline initial submission, normal replacement, review during replacement drafting, persisted refusal, explicit new submission and retained review history.
- Initial E2E runs exposed outdated file-picker and review-list selectors, now updated. The reload step waits for durable refusal before reopening. One combined Firefox run stopped at the existing authentication safety screen before recovery; the unchanged isolated Firefox rerun passed.
- Mobile screenshots at 320/390 CSS px are included for all three engines; the recovery button has a separate line.
- No backend change or migration. No production state changed.
