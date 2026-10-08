# Объединённый выпуск ВМШ и TLF — 8 октября 2026

Владелец разрешил объединить четыре доработки, прогнать тесты, закоммитить,
запушить и выпустить один результат на оба production портала.

## Состав и сохранение исходников

Исходный head: `55ed5e9c`. Перед изменениями сохранены бинарные patches,
незакоммиченные файлы и SHA-256 manifests в локальной `.runtime/integrate-20261008/source-snapshots`.
Все три исходных worktree были idle; другие ветки и активная Zoom-работа вне scope.

- `0d8f0d73`: [браузерные изображения](browser-image-uploads.md),
  [shared uploader](../../vmshpwa/packages/app-shell/src/image-upload-client.ts).
- `7a97624e`: [полная переписка проверок](../../vmshpwa/docs/review-history.md),
  [проекция истории](../../models/pwa/review_conversation.py).
- `0d5e46f2`: [публичный домен](../../vmshpwa/docs/public-media-domain-20261008.md).
- `b9656500`: [надёжность и производительность](2026-10-08-fixes.md).

Неприменённые новые migrations перенумерованы в единую зависимую цепочку:
[0114](../../migrations/0114.browser_image_uploads.py) →
[0115](../../migrations/0115.vmsh_public_media_domain.py) →
[0116](../../migrations/0116.notification_push_candidate_index.py).
Schema fixtures и ожидаемые heads обновляются из реальной объединённой схемы.

## Проверка и выпуск

Статус: объединение завершено, release gate и production preflight в работе.
Точная квитанция общего gate, source digest, public smoke, backups и runtime
heads будут добавлены после фактических проверок. Прежние отдельные PASS/FAIL
не заменяют проверку объединённого результата.

Direct upload остаётся disabled для Beget: провайдер не доказал SHA-256/HEAD
checksum. Современные браузеры используют подготовленный WebP через лёгкий
proxy без повторного кодирования. Production credentials, course settings,
личные ответы и материалы не переносятся из тестовой среды.
