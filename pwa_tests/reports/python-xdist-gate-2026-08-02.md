# Python test gate with eight isolated workers

Date: 2026-08-02

## Result

`make python-test` is the complete hermetic Python gate. It deliberately runs
the two suites one after another, with eight `pytest-xdist` workers in each:

1. `tests` — the legacy Telegram/domain regression;
2. `pwa_tests` — the PWA domain/API/migration/tooling regression with the
   explicit `pwa-e2e` runtime profile.

They are not collected by one pytest invocation. Their `conftest.py` files set
different import-time runtime profiles, so mixing both trees in one collection
can make PWA modules inherit legacy configuration. Sequential suite commands
keep the intended boundaries and still parallelize the actual tests.

## Database isolation

- Legacy database tests include the xdist worker ID in their temporary SQLite
  filename (for example `unittest_gw3.db`) or use pytest's worker-local
  `tmp_path`.
- PWA tests create and migrate one temporary SQLite through each worker's
  session-scoped `tmp_path_factory`; they do not use persistent
  `db/vmshpwa_e2e.sqlite3`.
- Live NATS/S3/Telegram smokes remain separate explicit commands and are not
  hidden inside this hermetic gate.

## Small compatibility fixes

- Legacy user fixtures now expect the already existing nullable `public_id`
  column.
- The old group-field guard now matches code access forms such as
  `row['level']`/`level_id`, while the existing schema test remains responsible
  for proving that the removed column is absent. It no longer rejects unrelated
  words such as logging level, heading level or compression level.
- Synthetic subprocess probes use a five-second test-only startup allowance so
  eight busy workers do not misclassify an immediate non-zero exit as a timeout.
  The dedicated 50 ms timeout assertion remains unchanged. Production probe
  timeouts were not modified.

## Measured proof

Final `make python-test` on the development Mac:

```text
legacy: 121 passed, 1 skipped in 12.87 s
PWA:    1542 passed, 5 skipped in 69.55 s
total:  85.53 s wall time
```

The skips are intentional environment/capability cases. Remaining warnings are
the existing SymPy deprecation and openpyxl's unsupported data-validation
extension notice.
