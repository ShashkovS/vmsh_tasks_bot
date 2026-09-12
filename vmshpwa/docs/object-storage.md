# Object storage: контракт этапа 0

## Граница

`helpers/object_storage.py` — единственная server-side граница файловых/S3
объектов. Домен и будущие aiohttp upload endpoints используют общий
`ObjectStorage.put/get/delete/public_url`; браузер всегда отправляет файлы через
aiohttp и не получает S3 write credentials или presigned upload URL.

Метаданные, связи, версии attachment и audit остаются в SQLite. Сам object key
не заменяет `media_assets.public_id` и не является правом доступа. Публичный GET
допустим для длинных непредсказуемых submission keys, но список объектов и
операции записи остаются закрытыми.

## Ключи и файловый адаптер

`canonical_object_key()` принимает только canonical POSIX relative key:

- без абсолютного пути, `.`/`..`, пустых segments, backslash, NUL/control chars;
- не длиннее S3-предела 1024 UTF-8 bytes;
- с одинаковой семантикой для filesystem и S3.

S3-адаптер повторяет 1024-byte проверку после добавления runtime prefix: лимит
провайдера относится ко всему итоговому key, а не только к доменному суффиксу.

`content_addressed_key(namespace, bytes, extension)` строит ключ
`<namespace>/sha256/<2>/<2>/<sha256>.<ext>`. Он предназначен для переиспользуемых
LaTeX/TikZ/SVG/WebP derivatives. Submission photographs получают отдельные
непредсказуемые revision keys на этапе 5 и не дедуплицируются между учениками.

`LocalObjectStorage` закрепляет все обходы каталогов через directory file
descriptors и `O_NOFOLLOW`, отклоняет symlink root/parent/object и не следует за
ними при get/put/delete. Запись идёт во временный sibling с restrictive mode,
`fsync`, atomic `os.replace` и directory `fsync`; сбой до replace сохраняет
предыдущий object. Agent/E2E media roots остаются разными согласно
[runtime isolation](runtime-isolation.md).

## S3-compatible адаптер

`S3ObjectStorage` использует актуальный lifecycle `aioboto3.Session().client()`
как async context manager. Каждый client получает явно:

- HTTPS `endpoint_url`;
- bucket без точек, безопасный для HTTPS virtual-host addressing;
- signing region;
- access/secret key;
- SigV4, virtual-host addressing и bounded standard retries;
- только обязательные request/response checksums (`when_required`) для
  совместимости с S3-провайдерами без optional flexible-checksum protocol;
- optional prefix и optional public CDN/CNAME origin.

Production target — Hetzner S3-compatible Object Storage, а выделенный test
bucket пока расположен в Beget. Адаптер знает ровно два документированных
endpoint-шаблона: `<region>.your-objectstorage.com` и
`s3.<region>.storage.beget.cloud`. Для них signing region выводится из hostname,
а public URL строится в virtual-hosted форме. Для любого другого совместимого
провайдера/CDN `s3_public_base_url` обязателен: adapter fail-fast отказывается
угадывать hostname. Полный object URL разрешён в media API там, где это
продуктовый контракт, но provider exception заменяется redacted boundary error,
поэтому URL/key не попадает в обычный log/Sentry traceback.

Первичные источники, проверенные 27 июля 2026 года:

- [aioboto3 usage: S3 client as async context manager](https://aioboto3.readthedocs.io/en/latest/usage.html);
- [Boto3 client configuration: region, SigV4, retry and S3 addressing](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/configuration.html);
- [Hetzner Object Storage overview and public URL format](https://docs.hetzner.com/storage/object-storage/overview/);
- [Hetzner public/private bucket semantics](https://docs.hetzner.com/storage/object-storage/getting-started/creating-a-bucket/);
- [Beget S3: endpoint, region и два формата публичного URL](https://beget.com/ru/kb/manual/obektnoe-hranilishche-s3-v-beget).

## Профили и secrets

`helpers/pwa/storage_config.py` намеренно не импортирует `helpers.config`, поэтому
storage-only command не инициализирует Telegram, Google, Sentry или legacy app.

- `pwa-human`, `pwa-agent`, `pwa-e2e`: только filesystem, credential files не
  читаются;
- `pwa-s3-integration`: только фиксированный test config
  `creds_test/vmsh_bot_config_test.json`, forced prefix
  `integration/<safe-run-id>`;
- `pwa-production`: только фиксированный production config, integration prefix
  запрещён;
- любой неизвестный профиль завершается ошибкой.

Из JSON извлекаются только `s3_url`, `s3_bucket_name`, `s3_region`,
`s3_access_key`, `s3_secret_key`, `s3_prefix`, `s3_public_base_url`. Старый
четырёхполевый overlay остаётся совместимым для private S3 operations: для
известных Beget и Hetzner endpoints signing region берётся из hostname, для
прочих старых провайдеров используется compatibility default `us-east-1`;
явное `s3_region` всегда имеет приоритет. Public smoke для неизвестного endpoint
дополнительно требует `s3_public_base_url`. Telegram/Google поля не
попадают в возвращаемый объект.

При выбранном S3 профиле endpoint, bucket, access и secret обязательны;
единый invariant действует и при прямом вызове dataclass-конструктора, поэтому
ambient AWS credential chain недоступен. Credential file читается через
удерживаемую цепочку directory/file descriptors с strongest available
`O_NOFOLLOW_ANY`/`O_NOFOLLOW`, `fstat` и повторной identity-проверкой; symlink,
hard-link, swap и файл больше 1 MiB отклоняются. Config `repr`/`safe_report()` не
содержат access/secret, bucket name, prefix, filesystem path или полный public
URL: bucket представлен только SHA-256 fingerprint, prefix — классом
`integration|configured|bucket-root`.

## Ручной live smoke

Smoke не входит в unit/E2E и никогда не запускается автоматически. Он разрешён
только владельцем для выделенного test bucket. До создания S3 client команда
сверяет endpoint и SHA-256 bucket name с owner-approved binding
`vmshpwa/fixtures/integration/s3-test-binding-v1.json`; одного имени
`creds_test` недостаточно для разрешения записи:

```bash
VMSH_ENABLE_LIVE_S3_TEST=true \
PWA_S3_RUN_ID=local-YYYYMMDD-unique \
make pwa-s3-live-smoke
```

Команда загружает один synthetic marker под forced
`integration/<run-id>/probe-<random>.txt`, сверяет private SDK read, делает обычный
public HTTP GET и запрашивает удаление object в `finally`. Delete предпринимается даже если
`PutObject` завершился client-side timeout: provider мог уже зафиксировать
объект. В stdout попадает только redacted capability result; credentials,
bucket, prefix key и полный public URL не печатаются. Результат `deleteAck=passed`
означает подтверждение S3 API, а не отдельный последующий HEAD/404 proof.
Production secret path
недоступен этой команде по конструкции.

## Growth и orphan inventory

Read-only команда [`media_inventory.py`](../scripts/media_inventory.py)
сравнивает `media_assets.object_key` и `news_media.storage_key` с filesystem или
настроенным S3 prefix. Точные ключи сохраняются только в owner-local manifest с
mode `0600`, stdout содержит агрегаты. Команда различает missing active object,
size mismatch, retained-deleted submission, unconfirmed news upload и object
без SQLite-ссылки; delete API у неё отсутствует.

Порядок запуска и интерпретация категорий описаны в
[media inventory и retention](media-inventory-and-retention.md). Один inventory
не является разрешением на удаление: бессрочная admin-managed retention требует
повторного preview, актуальной проверки БД, явного подтверждения и audit.

Если основная операция и cleanup завершаются ошибкой одновременно, обе
санитизированные причины сохраняются в `ExceptionGroup` и отдельно выводятся в
поле `causes`, а не маскируют друг друга. Случайный суффикс probe защищает от
перезаписи и удаления объекта параллельного повтора с тем же `run-id`. Команда
сообщает только run-id; оператор удаляет остаток именно внутри disposable
prefix.

27 июля 2026 года выполнен live smoke
`codex-phase0-20260727-f6c821d9`: pinned test binding, put, private read, public
GET и delete acknowledgement — PASS. До фиксации `when_required` botocore
получал безопасно диагностированный `XAmzContentSHA256Mismatch`; повтор после
исправления подтвердил совместимость установленного SDK и Beget. После
исправления collision safety второй live run
`codex-phase0-20260727-collision-safe` также прошёл все четыре шага.

## Реализация и проверки

- interface/adapters: `helpers/object_storage.py`;
- profile loader/redaction: `helpers/pwa/storage_config.py`;
- opt-in command: `vmshpwa/scripts/storage_smoke.py`;
- unit/hermetic integration: `pwa_tests/test_object_storage.py`;
- reproducible proof: `pwa_tests/reports/object-storage-phase0.md`.
