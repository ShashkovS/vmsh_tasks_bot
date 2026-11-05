# Instance branding

Decision, 2026-09-29: one codebase, independent deployments/databases. Brand
identity lives in the repository; global administrators select a profile at
`/staff/branding`. The choice is persisted in that instance's SQLite database.

## Implementation

- [Profile registry](../packages/contracts/src/brand-profiles.json): names,
  default language, support address, colors and asset version. VMSh is the initial
  profile; TLF Prep Clubs defaults to English and `info@leaders.tech` support.
- [TLF assets](../brands/tlf-prep-clubs/v1): the owner's temporary SVG and derived
  installation icons. [UI tokens](../packages/ui/src/styles/globals.css) supply
  light/dark palettes. Fonts and semantic status/verdict colors are preserved.
- [Migration 0101](../../migrations/0101.pwa_branding.sql),
  [persistence](../../db_methods/pwa/branding.py) and
  [API](../../apps/pwa_api/branding_routes.py): singleton selection, admin-only
  updates, optimistic conflict detection and audit records.
- [Bootstrap](../packages/branding/src/index.ts) loads the public selection before
  rendering all four apps; [admin page](../apps/staff/src/branding-page.tsx)
  previews and selects profiles. Explicit device/account language choices win.
  Existing accounts retain their language during migration; new accounts inherit
  the selected default until they explicitly choose a language.
- [Build plugin](../vite-branding.ts) ships every profile's assets.
  [Manifest generator](../../helpers/pwa/branding.py) and
  [push icons](../packages/offline/src/push-branding.ts) use the selected profile.

Startup branding uses the shared [service transport](../packages/contracts/src/service-availability.ts)
and [translated waiting screen](../packages/branding/src/startup.ts). During a
502/503/504 or declared maintenance it retries automatically, including cold
starts and prolonged updates, before mounting a validated identity. The same
[real outage scenarios](../e2e/smooth-redeploy.spec.ts) cover runtime and branding.

Selection is revalidated on page load and cached locally for offline startup.
Changes apply on the next page load. Installed PWA name/icon refresh timing is
controlled by the browser; manifest URLs, application IDs and scopes stay stable.
Branding does not translate lesson content or rename existing account data.

## Enable on an independent deployment

1. Provision separate SQLite/analytics databases, media storage, NATS namespace,
   secrets, service/socket, origins and TLS for `prep.leaders.tech`. Do not reuse
   the original instance's databases or credentials.
2. Deploy backend and all four frontend builds together and run migration 0101
   through the normal migration flow. Ship the shared profile registry with the
   backend, since it reads that repository file.
3. Render/install the updated [nginx template](../deploy/nginx/vmshpwa.conf.template)
   and run the [nginx checks](../deploy/nginx/README.md). Stable Student/Family
   manifest URLs must proxy to the backend rather than serve the build fallback.
4. Log in as a global administrator, open **Оформление / Branding**, choose
   **TLF Prep Clubs**, and save. Verify an anonymous device opens in English and
   manifest icons resolve on the new origin.

TLF identity is deployed on `prep.leaders.tech`; see the
[deployment and live evidence](../../docs/deploy/tlf-app/README.md).
The VMSh instance retains its own default identity and explicit account locales.

## Certificate preparation — 2026-09-30

On SSH host `tlfprepagent` (`188.245.158.162`), both domains resolve to that
server over IPv4 and IPv6. Separate Let's Encrypt certificates were issued with
`certbot certonly --nginx`:

- `/etc/letsencrypt/live/prep.leaders.tech/fullchain.pem` and `privkey.pem`;
- `/etc/letsencrypt/live/grafprep.leaders.tech/fullchain.pem` and `privkey.pem`.

Both expire on 2026-12-29. The existing `snap.certbot.renew.timer` is active.
Certificate SANs/expiry were checked with OpenSSL; nginx configuration checks
passed, and configuration file checksums before/after issuance are identical.
Certificates were initially issued only. Grafana TLS and monitoring were then
[deployed and verified](../../docs/deploy/tlf-monitoring/README.md#deployed-and-verified--2026-09-30)
on 2026-09-30. [Clone deployment and live checks](../../docs/deploy/tlf-app/README.md)
are complete, with four healthy metric targets. Shared NATS monitoring remains
disabled to avoid restarting it. Existing services were preserved.

## Replace the temporary logo

Create a new version directory under `brands/tlf-prep-clubs/`, add the SVG and
192/512px PNGs plus a maskable 512px PNG with safe padding, then increment
`assetVersion` in the registry. Current PNGs were rendered with `rsvg-convert`
and ImageMagick; the maskable mark occupies a centered 352px square. Keep old
version directories available for cached clients. Build and deploy the assets
before a profile references their new version. Change profile metadata in the
registry and semantic brand colors in UI tokens; switching profiles applies the
registered default language to the database setting.

## Verification

- [Backend tests](../../pwa_tests/test_branding.py) cover selection, permissions,
  conflicts, audit, manifests, locale defaults and migration rollback;
  [auth integration tests](../../pwa_tests/integration/test_auth_http_api.py)
  cover inherited/explicit locale and request protections.
- [Browser scenario](../e2e/branding.spec.ts) passed in Chromium, Firefox and
  WebKit: admin selection, English landing/login pages, explicit Russian choice,
  public manifests/icons and restoring VMSh. Mobile captures were inspected.
- Five [Storybook scenarios](../apps/staff/src/branding-page.stories.tsx) passed;
  light/dark appearance inspected. Focused bootstrap, locale and push-icon unit
  tests, schema/nginx tests, typechecks, lint, catalog checks and all four
  production builds passed. No production data or visual baselines were changed.
