# Диагностика media storage и ручная retention

## Что делает команда

`vmshpwa.scripts.media_inventory` сравнивает фактические объекты filesystem или
S3 с двумя источниками object keys в SQLite:

- `media_assets.object_key` для content, generated assets и фотографий решений;
- `news_media.storage_key` для зеркальных Telegram-медиа.

Команда работает только на чтение. Она не меняет SQLite, не удаляет объекты и
не превращает диагностическую эвристику в автоматическую retention policy.
Точные ключи записываются в owner-local JSON с правами `0600` ниже
`.runtime/vmshpwa/media-inventory`; stdout содержит только агрегированные числа.

## Категории отчёта

- `missingActiveKeys` — активная SQLite-ссылка, для которой нет объекта;
- `sizeMismatches` — известный размер активного `media_assets` не совпадает;
- `retainedDeletedKeys` — фотография логически удалена до проверки, но согласно
  принятой бессрочной retention всё ещё хранится физически;
- `unconfirmedKeys` — у news media остался `pending|failed`, хотя объект виден;
- `unreferencedKeys` — ключ найден в storage, но отсутствует в обеих таблицах;
- `invalidDatabaseKeys` и `duplicateStorageKeys` — целостность inventory нельзя
  считать достаточной для последующей очистки.

Активная ссылка всегда сильнее остальных состояний того же ключа. Поэтому
объект не становится кандидатом лишь из-за второй `pending` или удалённой
строки, если он всё ещё нужен активному материалу.

## Локальный запуск

Люди используют human-профиль:

```shell
PWA_MEDIA_INVENTORY_REPORT=.runtime/vmshpwa/media-inventory/human-<run-id>.json \
make pwa-media-inventory
```

Агенты используют только изолированный agent-профиль:

```shell
PWA_MEDIA_INVENTORY_REPORT=.runtime/vmshpwa/media-inventory/agent-<run-id>.json \
make pwa-agent-media-inventory
```

Для production S3 та же Python-команда запускается под настоящим service
profile с `VMSH_ENABLE_MEDIA_INVENTORY=true`. Она использует только
`ListObjectsV2` для настроенного prefix и открывает SQLite через `mode=ro`.
Bucket, credentials и полный prefix не попадают в stdout или committed proof.

## Что делать с результатом

Нулевые `missingActiveObjects`, `sizeMismatches` и integrity diagnostics —
readiness-сигнал. Ненулевые значения сначала расследуются; объект нельзя
удалять лишь потому, что он попал в одну категорию одного запуска.

`retainedDeletedKeys`, `unconfirmedKeys` и `unreferencedKeys` — только кандидаты
для будущего owner-reviewed cleanup. Перед удалением нужен повторный inventory
после согласованного интервала, preview точных объектов, проверка текущей БД,
явное подтверждение администратора и audit результата. Сам cleanup намеренно не
входит в эту команду: принятая политика хранит фотографии бессрочно до ручного
решения администраторов.

## Реализация и тесты

- команда: [`media_inventory.py`](../scripts/media_inventory.py);
- unit/integration boundary: [`test_media_inventory.py`](../../pwa_tests/test_media_inventory.py);
- Make-профили: [`Makefile`](../../Makefile);
- proof: [`phase11-media-inventory-2026-08-03.md`](../../pwa_tests/reports/phase11-media-inventory-2026-08-03.md).
