# Phase 2: live content-asset roundtrip

Дата проверки: 27 июля 2026 года.

## Что проверено

Guarded-команда
[`content_asset_storage_smoke.py`](../../vmshpwa/scripts/content_asset_storage_smoke.py)
использовала только выделенный test S3 profile и префикс
`integration/phase2-assets-20260727-a1/`. Она не читала production credentials,
не использовала учебный контент и не запускала Telegram/Google.

Два фиксированных synthetic source прошли целевой pipeline:

- TikZ → `pdflatex` → `pdf2svg` → sanitized SVG: 3331 bytes, 67×67;
- PPM raster → ImageMagick normalize/strip → `cwebp`: 82 bytes, 4×2.

Для каждого результата до сетевой записи проверен SHA-256, затем выполнены:

1. `PutObject` в test bucket;
2. приватное чтение через S3 adapter и точное сравнение bytes;
3. credential-free public GET `200` и точное сравнение bytes;
4. удаление в `finally`.

Оба объекта получили `put/privateRead/publicGet/deleteAck = passed`; после
проверки тестовые объекты удалены. Отчёт не содержит credentials, object URLs
или исходный контент; только synthetic hashes, размеры и безопасный fingerprint
test binding.

## Команда и результат

```text
VMSH_ENABLE_LIVE_S3_TEST=true \
PWA_S3_RUN_ID=phase2-assets-20260727-a1 \
make pwa-content-assets-live-smoke

ok: true
syntheticOnly: true
tikz-svg: put/read/public-GET/delete passed
raster-webp: put/read/public-GET/delete passed
```

Machine-specific executable paths передавались только через локальное
окружение и не сохраняются в repository/provenance.

## Герметичные доказательства

```text
uv run pytest -q -n0 \
  pwa_tests/test_content_asset_storage_smoke.py \
  pwa_tests/domain/test_content_asset_service.py
13 passed
```

Тесты покрывают opt-in guard, pinned profile, два типа assets, точное private и
public чтение, cleanup после основной ошибки, одновременную ошибку
operation+cleanup, безопасную редакцию provider error messages и отказ до S3/DB при
противоречивом converter hash.

Реальный локальный converter smoke отдельно прошёл:

```text
uv run pytest -q -n0 pwa_tests/integration/test_content_assets_smoke.py
1 passed
```

Этот proof закрывает live content-asset storage roundtrip, но не весь Phase 2:
HTTP asset upload/matching, orphan reconciliation после DB failure и
production/staging service-account toolchain остаются отдельными gates.
