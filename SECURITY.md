# Security Policy

## Supported Versions
The repository does not publish tagged releases. Security fixes are applied to the `main` branch and should be deployed from that branch after review. Historical release metadata was not found in the git history.

## Reporting a Vulnerability
- Please open a private security advisory or a confidential GitHub issue addressed to the maintainers (e.g. @ShashkovS) with the details of the vulnerability.
- Provide clear reproduction steps, the scope of impact, and any temporary mitigations you have applied.
- Do not publicly disclose the issue until the maintainers confirm a fix has been deployed to production instances.

## Handling secrets
- Never commit real Telegram tokens, Google service account JSON files, or database dumps. Place sensitive data under `creds_test/` or `creds_prod/` with correct filesystem permissions instead of tracking them in git.
- Rotate the `telegram_bot_token`, `sos_channel`, and `exceptions_channel` values in the JSON configuration if you suspect the bot credentials have leaked.
- Set the `PROD` environment variable to `true` only on production hosts so that the application loads the production configuration and webhook endpoints.

## Hardening guidance
- Keep SQLite (≥3.35) and Python (≥3.9) patched, matching the versions described in `docs/deploy.md`.
- Run the aiohttp services behind TLS-terminating infrastructure (nginx or similar) as described in `docs/deploy.md`.
- Enable and monitor the logging channels configured in `helpers.config` so that bot failures surface quickly.
- When using the game web interface, keep a NATS server available and restrict it to trusted networks, because it broadcasts unencrypted updates to subscribers.
