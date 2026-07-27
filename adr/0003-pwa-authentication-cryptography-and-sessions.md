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
Production Student activation remains gated by the exposure/rotation questions
in `vmshpwa/dev/development-plan/20-implementation-questions.md`.

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

- Unsafe cookie-authenticated requests require an allowed `Origin`, with a
  strict `Referer` fallback for clients that omit Origin, plus Fetch Metadata
  rejection where available. Public origin and trusted proxy hops are explicit
  configuration; arbitrary forwarding headers are ignored.
- nginx limits by network source. SQLite `auth_throttle_buckets` additionally
  limits normalized-login/account buckets across all aiohttp workers. Bucket
  keys are peppered HMACs, never raw logins.
- Authentication responses and timing do not reveal whether an account exists.

## Current primary references

Checked on 2026-07-27:

- [argon2-cffi PasswordHasher API](https://argon2-cffi.readthedocs.io/en/stable/api.html)
  and [parameter guidance](https://argon2-cffi.readthedocs.io/en/stable/parameters.html);
- [itsdangerous serializers](https://itsdangerous.palletsprojects.com/en/stable/serializer/),
  [timed signatures](https://itsdangerous.palletsprojects.com/en/stable/timed/)
  and [key/salt concepts](https://itsdangerous.palletsprojects.com/en/stable/concepts/);
- [aiohttp cookie API](https://docs.aiohttp.org/en/stable/_modules/aiohttp/web_response.html);
- [MDN Set-Cookie reference](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Set-Cookie);
- [W3C Fetch Metadata](https://www.w3.org/TR/fetch-metadata/);
- [OWASP CSRF Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html).

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
