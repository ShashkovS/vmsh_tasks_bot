# ADR 0003: PWA credentials, cookies and revocable sessions

- Status: accepted for Phase 1 implementation
- Date: 2026-07-27
- Scope: Student, Family and Staff web authentication

## Context

The three browser applications share one aiohttp/SQLite deployment while
remaining separate security audiences. Student credentials are the current
Telegram token; Family and Staff use separately provisioned passwords. The
deployment currently has two workers, so login throttling, refresh rotation and
revocation cannot rely on process memory.

The repository also contains legacy plaintext/token-shaped data. It is not a
source for fixtures and it is not copied into a second plaintext auth field.
The owner accepted the historical migration/repository exposure risk on
2026-07-27: current activation reads the authoritative user credential,
requires the existing aggregate preflight and never reuses migration-carried
rows. Rewriting Git history or rotating otherwise valid accounts solely because
of migration `0038` is outside this phase.

## Decision

### Credentials

- Every web credential is stored as Argon2id using `argon2-cffi` 25.1 or newer.
  Production uses `PasswordHasher` defaults. Tests inject a cheaper hasher;
  there is no runtime switch that weakens production parameters.
- Successful verification calls `check_needs_rehash`; a stale hash is replaced
  in the same authenticated state transition.
- Login normalization is Unicode NFKC, trim, casefold and collapsed whitespace.
  Student token normalization additionally preserves the historical bot
  homoglyph mapping from `models/user.py`.
- Student username algorithm v1 is a frozen local Cyrillic transliteration plus
  zero-padded birth day: `transliterated-surname-DD`. A collision blocks import
  until an explicit stored override is approved. Row-order or numeric-ID
  suffixes are forbidden because they make an identity unstable.

### Sessions and cookies

- Login creates an opaque refresh secret and a short signed access cookie.
- Only an HMAC-SHA-256 digest of the refresh secret is stored in SQLite. The
  pepper is independent from access-cookie signing keys.
- The access payload contains only version, opaque account/session references,
  audience, credential version and session version. Roles and permissions are
  reloaded from authoritative storage.
- `itsdangerous.URLSafeTimedSerializer` uses a different salt per audience.
  Signing keys form an oldest-to-newest rotation list; the newest key signs.
- Access lifetime is 15 minutes for the initial implementation. Refresh/session
  expiry is the next 10 August 00:00 in `Europe/Moscow`, stored in UTC.
- Refresh is single-use rotation with an optimistic session version. Each
  consumed HMAC is retained only until that session expires. A mismatch revokes
  the lineage only when it matches this bounded consumed-HMAC history; an
  arbitrary invalid secret is not mislabeled as replay and cannot revoke a
  session merely from its public ID. Raw refresh secrets are never retained.
- Revocation is soft (`revoked_at`, reason, version increment) and is accompanied
  by a secret-free `auth_events` row. This preserves device/history UX and
  incident evidence. Cleanup is a later retention operation, not logout.
- Audience cookies use separate names and paths, `HttpOnly`, `SameSite=Lax`, and
  `Secure` in production. Cookie Path limits browser delivery but is not treated
  as an authorization boundary.

### Request protection and throttling

- Every unsafe browser request under an audience path, including login before
  cookies exist, requires an allowed `Origin`, with a strict `Referer` fallback
  for clients that omit Origin, plus Fetch Metadata rejection where available.
  The exact safe set is `GET`, `HEAD` and `OPTIONS`; an unexpected `TRACE` is
  handled as unsafe and the PWA adapter exposes no TRACE route.
- Audience WebSocket handshakes are authenticated cookie-bearing GET requests,
  so they are the explicit safe-method exception: every handshake requires an
  exact allowlisted browser `Origin` before upgrade. The connection is mapped
  after upgrade to its server-verified audience/account/session. Every
  post-register write and close shares one bounded per-socket lock. Revoke,
  logout and logout-all close local matches and publish an exact versioned NATS
  session/account close command; invalid or extension-bearing commands are
  ignored. If transient fan-out fails, periodic SQLite revalidation closes the
  connection rather than trusting the initial cookie forever.
- Refresh-only logout may request immediate socket close only when the
  repository has constant-time verified the current refresh HMAC or bounded
  consumed-HMAC history and returned an internal account/session target. A
  malformed, arbitrary, foreign or already-revoked refresh cookie returns the
  same public `204` but never becomes an owner-scoped close command.
- Public origin and trusted proxy hops are explicit configuration. Forwarding
  headers are rejected unless the immediate peer and exact chain length match
  that configuration. When RFC 7239 `Forwarded` is enabled, the deployment
  contract requires the client-facing trusted proxy to replace, rather than
  append to, the header and put the external `host` and `proto` in its first
  element. This convention is verified against the production nginx config;
  it is not inferred from arbitrary RFC 7239 chains.
- The immediate application-facing proxy may use either an explicitly
  configured IP network or an exact canonical filesystem `AF_UNIX` socket
  path. A Unix transport is not trusted merely because it is local: aiohttp's
  transport socket family and server-side `sockname` must match the allowlist,
  the forwarding hop count remains exact, and the socket directory/mode is an
  operating-system deployment boundary. Abstract, relative, normalized-alias
  and merely "other local" sockets are rejected. For more than one proxy hop,
  the other proxy addresses still need explicit trusted networks.
- nginx limits by network source. SQLite `auth_throttle_buckets` additionally
  limits normalized-login/account buckets across all aiohttp workers. Bucket
  keys are peppered HMACs, never raw logins.
- Authentication responses and timing do not reveal whether an account exists.

### Authorization

- Legacy user types are exact enum values. In particular, negative archived or
  deleted types are never interpreted as Staff through bitwise membership.
- A legacy admin is global. A teacher has only the course-wide or group scopes
  currently loaded from `staff_scopes`; a row whose local role says `admin`
  does not promote that teacher to global admin.
- Route parameters are not proof of membership. Student/Family authorization
  combines ownership with authoritative enrollment rows. Staff services first
  load the requested resource or membership and then authorize its persisted
  course/group scope. Collection queries must apply the teacher's scopes in
  SQLite and cannot pass on a bare capability check.
- Missing, malformed or contradictory identity/access rows fail closed. UI
  hiding is never an authorization boundary.

## Current primary references

Checked on 2026-07-27:

- [argon2-cffi PasswordHasher API](https://argon2-cffi.readthedocs.io/en/stable/api.html)
  and [parameter guidance](https://argon2-cffi.readthedocs.io/en/stable/parameters.html);
- [itsdangerous serializers](https://itsdangerous.palletsprojects.com/en/stable/serializer/),
  [timed signatures](https://itsdangerous.palletsprojects.com/en/stable/timed/)
  and [key/salt concepts](https://itsdangerous.palletsprojects.com/en/stable/concepts/);
- [aiohttp cookie API](https://docs.aiohttp.org/en/stable/_modules/aiohttp/web_response.html);
- [aiohttp proxy security guidance](https://docs.aiohttp.org/en/stable/web_advanced.html#deploying-behind-a-proxy)
  and [request transport access](https://docs.aiohttp.org/en/stable/web_reference.html#aiohttp.web.BaseRequest.transport);
- [Python 3.14 socket address and AF_UNIX semantics](https://docs.python.org/3/library/socket.html#socket-families);
- [nginx proxy header replacement/suppression](https://nginx.org/en/docs/http/ngx_http_proxy_module.html#proxy_set_header),
  [WebSocket proxying](https://nginx.org/en/docs/http/websocket.html) and
  [request limiting](https://nginx.org/en/docs/http/ngx_http_limit_req_module.html);
- [MDN Set-Cookie reference](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Set-Cookie);
- [W3C Fetch Metadata](https://www.w3.org/TR/fetch-metadata/);
- [OWASP CSRF Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html);
- [OWASP WebSocket Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/WebSocket_Security_Cheat_Sheet.html).

## Consequences

- The service requires independently managed access-signing keys, refresh HMAC
  pepper and throttle HMAC pepper outside the repository.
- Immediate revoke checks require a small SQLite read for protected requests;
  a valid signature alone is insufficient.
- Student token reset must atomically update its Argon2 hash, increment
  `credential_version`, revoke sessions and keep the legacy Telegram adapter in
  sync until that adapter no longer stores the token.
- `signons.token` must not receive PWA credentials. PWA login audit uses
  `auth_events`; any required legacy compatibility projection must be
  secret-free.
- A production Unix deployment must keep the rendered nginx upstream path and
  `VMSH_PWA_TRUSTED_PROXY_UNIX_SOCKETS_JSON` byte-for-byte aligned and protect
  the socket with a dedicated directory/group. Loopback TCP remains supported
  for controlled hosts, but loopback by itself does not identify a local
  process and is therefore not the preferred production boundary.
