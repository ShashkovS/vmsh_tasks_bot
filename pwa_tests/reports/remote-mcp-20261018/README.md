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

## Deployed and verified

Owner unlocked the normal SSH key. Ordinary SSH push published application
`450903b77351627b50f9845fca9a5d7abb66880d` to `vmshpwa`. VMSH installed webhook
and the existing guarded TLF workflow completed successfully, without migrations.

- VMSH static `450903b77351-20261018173406`: [production proof](vmsh-production-proof.json).
- TLF static `tlfprep-20261018-remote-mcp-450903b77351`: [production proof](tlf-production-proof.json), [backup/data/guard](tlf-rollout.json).
- Each: 25 read-only HTTP checks, 4 HTML / 119 Staff hashes, production provenance,
  SQLite quick_check, required existing schema, private MCP/token APIs 401 and
  native remote MCP 401 without Origin. Services active, maintenance off.
- TLF: all 171 business tables unchanged while writers were stopped, canonical
  settings and NATS preserved, verified backups before/after, PWA/Zoom active.
  The legacy main Telegram process remains inactive. No new schema migration.
- [Verifier](verify-production.py) checks the public endpoint through existing nginx;
  no nginx/systemd changes or extra listeners were installed. MCP is in the default
  production dependency set. No permanent user key was minted for deployment;
  positive authentication/images/proposals are covered by the real isolated SDK
  integration and normal review E2E, not a privileged production write probe.

Connect from any folder without a clone, Python or local subprocess:

```toml
[mcp_servers.vmsh-review]
url = "https://vmsh.shashkovs.ru/staff/api/ai-review/v1/mcp"
http_headers = { Authorization = "Bearer air_YOUR_PERSONAL_KEY" }
```

For TLF use another connection name, `https://prep.leaders.tech/staff/api/ai-review/v1/mcp`
and a personal TLF key. Existing unexpired portal keys remain valid.
[Full instructions](../../../vmshpwa/docs/ai-review-assistant.md#подключение-именно-в-codex).
