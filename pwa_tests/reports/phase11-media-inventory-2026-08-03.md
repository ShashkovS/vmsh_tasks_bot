# Phase 11: read-only media growth and orphan inventory

Дата проверки: 3 августа 2026 года.

## Реализованная граница

- Одна maintenance-команда сравнивает migration-head SQLite с filesystem или
  настроенным S3 prefix.
- Единственные источники ссылок названы явно: `media_assets.object_key` и
  `news_media.storage_key`; сканирование произвольных text-колонок отсутствует.
- Активные, логически удалённые и незавершённые ссылки различаются. Активная
  ссылка на тот же key всегда запрещает классифицировать объект как cleanup
  candidate.
- Exact keys остаются только в owner-local manifest ниже
  `.runtime/vmshpwa/media-inventory` с mode `0600`. Обычный вывод содержит лишь
  counts/bytes и разбиение активных ссылок по namespace.
- Команда не поддерживает delete. Это diagnostic/preview до будущего отдельного
  подтверждённого cleanup, а не новый автоматический retention worker.

## Проверки

- migration-head SQLite schema принимается;
- source SQLite byte-for-byte не меняется;
- filesystem fixture различает missing, size mismatch, retained-deleted,
  unconfirmed и storage-only object;
- один key с active и non-active ссылкой остаётся active;
- S3 `ListObjectsV2` проходит две страницы и снимает только точный configured
  prefix;
- owner manifest создаётся `0600`, не перезаписывается и не выходит из runtime
  root;
- CLI stdout не раскрывает точные keys;
- реальный `make pwa-agent-media-inventory` прошёл на изолированной agent-БД и
  media root: 0 objects, 0 active references, 0 diagnostics.

Focused результат: **6 passed**, Ruff format/check — **PASS**. Широкий
regression: frontend unit **114 файлов / 594 PASS**, Python PWA **1586 PASS / 6
intentional skips** в восьми workers; strict TypeScript — **PASS**.

Общий ESLint gate остановлен четырьмя ошибками в параллельно добавляемом, не
входящем в этот коммит `family-notifications-page.tsx`; media-inventory Python,
Make и docs файлов в ESLint scope нет. Ошибки не маскировались изменением
настроек и должны быть закрыты владельцем соседнего frontend-среза.

## Открытая production-граница

Этот инкремент закрывает software path обязательного growth/orphan report. Он
не утверждает состояние production Hetzner bucket: `ListObjectsV2` нужно
повторить под production service account непосредственно перед rollout и
сохранить owner-local manifest. Автоматическое или массовое удаление объектов
не реализовано и не разрешено этим proof.
