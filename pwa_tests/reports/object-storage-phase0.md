# Phase-0 object-storage proof

Дата: 27 июля 2026 года. Профиль: macOS, Python 3.14, hermetic filesystem,
in-memory recording S3 client и owner-approved Beget test bucket.

## Реализованный контракт

- `ObjectStorage.put/get/delete/public_url` и единая canonical key validation;
- content-addressed SHA-256 key helper для reusable content derivatives;
- atomic filesystem replacement с file/directory `fsync`;
- directory-fd/`O_NOFOLLOW` защита root, parent и object symlinks;
- explicit S3 endpoint/bucket/region/credentials/prefix через `aioboto3`;
- Hetzner/Beget virtual-host public GET, explicit public-origin override и
  fail-fast для неизвестной public URL topology;
- allowlisted test/production secret source без импорта Telegram/Google config;
- forced disposable `integration/<run-id>` и cleanup-on-failure smoke workflow;
- уникальный probe key на каждый запуск, включая повторы одного `run-id`;
- обе обезличенные причины доступны оператору при совместном сбое операции и
  cleanup;
- pinned endpoint + SHA-256 bucket identity до создания live client;
- optional flexible checksums отключены через documented `when_required`, при
  этом SigV4 и обязательные checksums сохранены;
- redacted config/adapter representations and operational report.

## Проверки

После реализации выполнены:

- `uv run ruff check helpers/object_storage.py helpers/pwa/storage_config.py vmshpwa/scripts/storage_smoke.py pwa_tests/test_object_storage.py pwa_tests/integration/test_object_storage_contract.py` — PASS;
- `uv run pytest -n0 pwa_tests/test_object_storage.py pwa_tests/integration/test_object_storage_contract.py pwa_tests/test_pwa_app.py` — **86 passed**;
- `git diff --check` — PASS.

Проверяются safe/canonical keys, stable hashes, put/get/delete parity, failed
replace, partial-read absence, symlink escape, partial config, fixed source
selection, filesystem no-secret-read, redaction, explicit S3 client arguments,
public URL encoding, exact opt-in, pinned live identity, checksum config,
provider-error redaction без hidden exception context и cleanup после
public-read failure, collision-safe повтор одного run-id и полный redacted CLI
report при двойной ошибке.

Live run `codex-phase0-20260727-f6c821d9`:

- pinned test endpoint/bucket identity — PASS;
- `PutObject` — PASS;
- private SDK read и byte equality — PASS;
- public HTTPS GET и byte equality — PASS;
- `DeleteObject` acknowledgement в `finally` — PASS.

После независимого ревью collision-safe key повторно проверен live run
`codex-phase0-20260727-collision-safe`: put, private read, public GET и delete
acknowledgement — PASS.

## Не выполнено сознательно

- aiohttp upload endpoint, media DB rows, immutable submission revisions и
  retention cleanup относятся к фазам 2/5;
- production capability/readiness probe относится к фазе 11.

## Локальная конфигурационная находка

Без чтения/печати bucket и credentials проверен hostname текущего test overlay:
`s3.ru1.storage.beget.cloud`. После сверки с первичной документацией Beget этот
точный endpoint получил узкую поддержку signing region `ru1` и virtual-hosted
public URL. Идентичность bucket закреплена только SHA-256, без публикации имени.
Неизвестные provider-specific URL adapter по-прежнему не угадывает.
