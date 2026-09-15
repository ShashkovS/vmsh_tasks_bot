# Compact record identifiers

Status: accepted owner decision, 22 August 2026.

The PWA has a small, trusted educational audience. Persistent record IDs are
not secrets and do not need random, opaque public copies. Each PWA table uses
its existing `INTEGER PRIMARY KEY` as the SQLite rowid and exposes a compact,
deterministic identifier derived from that number. The displayed and API form
is `<prefix>-<id>`: for example `u-127`, `c-912`, `g-627`, `gl-13`, and
`cr-1`.

`public_id` remains a **virtual generated column** only while the Python API
and TypeScript wire contracts use that field name. It stores no duplicate text
in the table and has no uniqueness index: the table name/prefix and integer
primary key already make it unique. Relations stay integer foreign keys. This
keeps the change local to storage and creation paths while preserving readable
URLs, optimistic-lock ETags, and contract field names.

The initial compact prefixes are:

| Records | Prefix |
| --- | --- |
| users, accounts, seasons, courses, groups | `u`, `a`, `s`, `c`, `g` |
| enrollments, enrollment events, staff scopes | `en`, `ene`, `ss` |
| course/group lessons, schedules, lesson windows, publications | `cl`, `gl`, `sr`, `so`, `lw`, `lp` |
| content source/revision, media asset, problem/synonym | `cs`, `cr`, `ma`, `p`, `ps` |
| attempts, submission thread/entry/attachment/reassignment | `ta`, `st`, `se`, `sa`, `sra` |
| review, annotation and review events | `r`, `ra`, `re` |
| classroom catalog event, in-person event, layout/plan/delivery | `room`, `ce`, `ipe`, `clv`, `cap`, `cdb` |
| support, notification, Telegram binding, news, audit | `sup`, `sue`, `n`, `tb`, `news`, `ae` |

Random values remain where unpredictability is a security or deduplication
property rather than a record identity: auth session and refresh secrets,
password/token hashes, idempotency keys, lease/claim tokens, and untrusted
file-upload temporary names. These are not exposed as compact record IDs.

The owner will start from a fresh database, so historic data conversion and
compatibility with opaque values are deliberately out of scope. The source of
truth for the implementation is the migrations in [`../../migrations`](../../migrations),
the generated schema artifacts in [`../../pwa_tests/fixtures`](../../pwa_tests/fixtures),
and the public Zod contract in
[`../packages/contracts/src/auth.ts`](../packages/contracts/src/auth.ts).
