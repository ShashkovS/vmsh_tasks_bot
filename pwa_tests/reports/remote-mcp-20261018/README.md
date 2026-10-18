# Remote MCP — 18 October 2026

Owner requested HTTP MCP without a local checkout and authorized continuing the
existing deployment on both production sites. [Contract and Codex setup](../../../vmshpwa/docs/ai-review-assistant.md#подключение-без-клона-репозитория).

Implementation: [aiohttp endpoint](../../../apps/pwa_api/ai_review_mcp_routes.py),
[shared dispatch](../../../apps/pwa_api/ai_review_routes.py),
[real SDK integration](../../integration/test_ai_review_remote_mcp.py).
No schema changes; MCP SDK moves into default production dependencies.
[TLF guarded release](deploy-tlf.sh) requires an unchanged migrations directory,
verified backups, static provenance, stopped-writer business parity and runtime
checks. VMSH uses only normal SSH push and its installed webhook.

[Fast gate](fast-gate.json) PASS: 3086 Python / 12 SKIP, 1142 frontend,
384 Storybook, 45 Chromium E2E; format/types/lint/i18n/build PASS, source unchanged.
Three real SDK remote HTTP scenarios passed, including native clients without Origin,
images, proposals, bulk context, fresh scopes, revocation and concurrent identities.
Production deployment pending: the configured GitHub key is accepted by GitHub,
but macOS Keychain reports `User interaction is not allowed`. The owner was
asked to unlock the Mac/keychain. Only normal SSH commit/push/autodeploy will
be used; both sites retain `19056ec7` until this continuation is published.
