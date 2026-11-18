# TikZ SVG rollout — 3 November 2026

Owner-authorized deployment to the current VMSh Timeweb host and TLF.
Application commit: `35c0a6ab81cfa5794a897227847f5cb43da56b57`, based on
the existing production source `3ddb0a8e`.

[`assets.py`](../../../helpers/pwa/content/assets.py) ignores TeX comments
when choosing Cyrillic fonts and preserves the full SVG vocabulary emitted by
our `pdf2svg` for TikZ/PDF conversion. Direct SVG uploads retain sanitization.
[Contract](../../../vmshpwa/docs/content-compiler-support-matrix.md#assets-и-внешний-toolchain).

Both deployments passed:

- Exact reported source `tikz-52fa6f5d8d036181` converted with the production
  toolchain; an actual Cyrillic label converted too.
- 25 read-only public HTTP checks per site.
- Verified online main/analytics SQLite backups before switching.
- Graceful PWA worker handover on both hosts and Telegram worker handover on
  VMSh; configuration, schema, static symlinks and NATS retained.
- Publication used ordinary Git push/fetch; Timeweb used HTTPS fetch because
  its service account lacks GitHub SSH host trust. No trust checks disabled.

[VMSh receipt](vmsh-production.json), [TLF receipt](tlf-production.json).
Private backups, deployment script and conversion logs remain on each host at
`/web/vmsh_tasks_bot/deploy/releases/tikz-svg-20261103-35c0a6ab81cf/`.
Rollback uses `git reset --keep` to the recorded source followed by graceful
worker replacement; it preserves unrelated local repairs and never restores
an old database over live writes. There were no migrations or dependency changes.

Validation: 38 focused TikZ/assets tests and real conversion of all three
figures in the supplied file passed. The final broad run reached 3113 Python
PASS / 12 SKIP, 1142 frontend PASS and 384 Storybook PASS; formatting, types,
lint and i18n passed. One pre-existing SQLite plan expectation was explicitly
excluded: SQLite 3.53.1 optimizes its EXISTS query using an automatic partial
covering index rather than the expected correlated full scan.

The owner explicitly requested stopping the broad tests and proceeding with
the focused checks. E2E was interrupted, so the overall fast gate is **not**
reported as PASS. Receipt:
`.runtime/vmshpwa/checks/20261103T215924.643165Z/summary.json`.
