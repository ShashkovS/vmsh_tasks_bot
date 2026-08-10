# Production PWA systemd profile

This directory contains the separate PWA API service profile. The existing
Telegram webhook service remains a parallel adapter over the same SQLite and is
not replaced or started by this unit. Google credentials are not loaded by the
`pwa-production` profile.

## Render and install

1. Render every `@@...@@` marker in `vmshpwa.service.template` into
   `/web/vmsh_tasks_bot/vmshpwa/runtime`.
   The socket, environment file and unit source stay under this directory.
2. Keep the environment file owned by `vmsh_tasks_bot:vmsh_tasks_bot` with mode `0600`.
   It contains only the nginx -> PWA transport boundary. Application settings
   and secrets live in `creds_test/vmsh_bot_config_test.json` or
   `creds_prod/vmsh_bot_config_prod.json`. Do not create a second production
   settings file under the deployment directory.
3. The database directory, media root and runtime-write directory must already
   exist and be writable by `@@SERVICE_USER@@`. The repository and virtual
   environment remain read-only to the service.
4. Render the same backend Unix-socket path into nginx and
   `VMSH_PWA_TRUSTED_PROXY_UNIX_SOCKETS_JSON`.
5. Validate before installation:

   ```shell
   VMSH_PWA_SYSTEMD_UNIT=/web/vmsh_tasks_bot/vmshpwa/runtime/vmshpwa.service \
   VMSH_PWA_SYSTEMD_ENV=/web/vmsh_tasks_bot/vmshpwa/runtime/vmshpwa.env \
   make pwa-systemd-check
   ```

6. Expose the unit to systemd with a symlink; the unit source remains in the
   deployment root:

   ```shell
   sudo systemctl link /web/vmsh_tasks_bot/vmshpwa/runtime/vmshpwa.service
   sudo systemctl daemon-reload
   ```

7. After `systemctl daemon-reload`, restart the PWA unit only after the explicit
   migration command has completed under the exclusive database lock. Do not
   use a rolling Gunicorn reload for schema maintenance.

S3 settings are read from the allowlisted fields of
`creds_prod/vmsh_bot_config_prod.json`; they are not duplicated in this env
file. The PWA profile also reads `db_filename`, `nats_server`, `sentry_dsn`,
`pwa_instance`, `pwa_media_root`, `pwa_public_origins_json`,
`pwa_auth_signing_keys_json`, `pwa_refresh_pepper_b64` and
`pwa_throttle_pepper_b64` from that same JSON file. `sentry_dsn` is the backend
DSN; the frontend DSN is supplied separately at production build time as
`VITE_SENTRY_DSN`. Both may point to the same Sentry project. Web Push settings
(`pwa_vapid_public_key`, `pwa_vapid_private_key`, `pwa_vapid_subject`) are also
read from the profile JSON and must either all be filled or all be absent.

`EnvironmentFile=` values override `Environment=` values in systemd, so the
unit pins `VMSH_RUNTIME_PROFILE=pwa-production` and
`VMSH_PWA_PROTOTYPE=false` through `/usr/bin/env` in `ExecStart`. This follows
the current [systemd.exec environment precedence](https://www.freedesktop.org/software/systemd/man/latest/systemd.exec.html#EnvironmentFile=)
instead of relying on directive order.

The local structural checker deliberately does not claim that systemd can start
the unit. On the Linux host `make pwa-systemd-check` requires
`systemd-analyze verify`; the final rollout gate additionally requires a real
restart, health checks through nginx and rollback to the previous release.
