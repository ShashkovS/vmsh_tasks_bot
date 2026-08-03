# Production PWA systemd profile

This directory contains the separate PWA API service profile. The existing
Telegram webhook service remains a parallel adapter over the same SQLite and is
not replaced or started by this unit. Google credentials are not loaded by the
`pwa-production` profile.

## Render and install

1. Render every `@@...@@` marker in `vmshpwa.service.template` and
   `vmshpwa.env.example` into owner-controlled files outside the Git checkout.
2. Keep the environment file owned by root or the service user with mode
   `0600`. It contains auth peppers, VAPID material and the Sentry DSN.
3. The database directory, media root and runtime-write directory must already
   exist and be writable by `@@SERVICE_USER@@`. The repository and virtual
   environment remain read-only to the service.
4. Render the same backend Unix-socket path into nginx and
   `VMSH_PWA_TRUSTED_PROXY_UNIX_SOCKETS_JSON`.
5. Validate before installation:

   ```shell
   VMSH_PWA_SYSTEMD_UNIT=/etc/systemd/system/vmshpwa.service \
   VMSH_PWA_SYSTEMD_ENV=/etc/vmshpwa/vmshpwa.env \
   make pwa-systemd-check
   ```

6. After `systemctl daemon-reload`, restart the PWA unit only after the explicit
   migration command has completed under the exclusive database lock. Do not
   use a rolling Gunicorn reload for schema maintenance.

`EnvironmentFile=` values override `Environment=` values in systemd, so the
unit pins `VMSH_RUNTIME_PROFILE=pwa-production` and
`VMSH_PWA_PROTOTYPE=false` through `/usr/bin/env` in `ExecStart`. This follows
the current [systemd.exec environment precedence](https://www.freedesktop.org/software/systemd/man/latest/systemd.exec.html#EnvironmentFile=)
instead of relying on directive order.

The local structural checker deliberately does not claim that systemd can start
the unit. On the Linux host `make pwa-systemd-check` requires
`systemd-analyze verify`; the final rollout gate additionally requires a real
restart, health checks through nginx and rollback to the previous release.
