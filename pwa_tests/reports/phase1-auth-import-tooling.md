# Phase 1 Student auth import tooling proof

Дата: 27 июля 2026 года.

Проверен контролируемый import на синтетических migrated SQLite copies. На
authoritative `db/vmsh.db` apply не выполнялся; реальные exclusions и collision
overrides не создавались.

- `pwa_tests/test_auth_import.py`: 16 сценариев (aggregate deterministic
  inventory/preview без Argon2, explicit exclusions/overrides, missing birthday
  и token, normalization+Argon2id, случайные раздельные public IDs,
  idempotent rerun, transactional rollback, source change между pre-hash и
  transaction, exact confirmation/dedicated target root, permissions,
  symlink/hardlink/authoritative guards, quiescent-sidecar guard, owner-only
  detail report).
- Production-size synthetic preview: 1617 rows, менее `1 s` на текущей машине,
  Argon2 hash/verify calls = 0; test gate оставляет запас до `5 s`.
- Локальная оценка production `argon2-cffi` defaults на синтетическом credential:
  3 hashes за `0.098 s`, в среднем `0.033 s`; линейная оценка 1549 pending rows
  около `0.8 min` до открытия write transaction и ещё около `0.8 min` на полную
  post-commit verification. Это эксплуатационная оценка, а не переносимый
  performance SLA.
- Aggregate output не содержит legacy IDs, login candidates, tokens или hashes.
- Detailed decision aid разрешён только под `.runtime/auth-import/`, имеет mode `0600` и не
  содержит token/hash.
- Apply использует all-at-once transaction; course enrollment/access/event
  backfill явно не принадлежит этому инкременту и не выполнялся.

Production activation остаётся открытым gate до появления утверждённого
owner-only decision file и rehearsal над отдельной production-size copy.
