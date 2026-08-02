# Phase 5: real written-photo media corpus

Дата: 2 августа 2026 года.

## Результат

Server fallback проверен не на поддельном ответе converter-а, а на настоящих
файлах, декодированных установленным production-like toolchain:

- JPEG `2600×1300` с EXIF orientation `6`, GPS и `UserComment`;
- HEIC `640×480`;
- PNG с прозрачностью и уже сжатый WebP;
- пять закреплённых по SHA-256 публичных фотографий математических материалов
  из переданного Telegram-export;
- компактный встроенный JPEG fixture с EXIF GPS, не требующий Pillow/ExifTool;
- повреждённая последовательность байтов;
- payload размером `25 MiB + 1 byte`.

JPEG после `-auto-orient` и ограничения длинной стороны стал WebP `960×1920`.
HEIC стал WebP `640×480`. В обоих результатах отсутствуют GPS и
`UserComment`; `cwebp -metadata none` проверен повторным чтением результата
через ExifTool. Исходные JPEG/HEIC и результаты существуют только во временном
каталоге pytest и удаляются вместе с ним.

Для пяти публичных фотографий дополнительно проверены исходные размеры,
ограничение 1920 px и свободный регрессионный SSIM-порог, защищающий от
сломанного encoder-а или случайного резкого снижения качества. Нормализованное
SSIM distortion оказалось в диапазоне `0.00156–0.00583`, gate требует `< 0.01`.
ImageMagick документирует `%[distortion]` как числовое значение выбранной
compare-метрики: [Command-line options](https://imagemagick.org/command-line-options/#compare).
Это не заменяет визуальное принятие владельцем.

Пять исходников закреплены SHA-256 и покрывают плотный портретный лист с
формулами, квадратную страницу, обычный портрет, широкую страницу и компактную
таблицу. Они остаются в ignored owner-local Telegram-export и не копируются в
репозиторий; при отсутствии экспорта эта дополнительная проверка пропускается.

Повреждённый файл отклонён на этапе `image-normalization`. Слишком большой
payload отклонён до запуска внешнего процесса с кодом `asset.raster_size`.

## Исполняемое доказательство

Тест:
[`pwa_tests/integration/test_content_assets_smoke.py`](../integration/test_content_assets_smoke.py).

Focused run:

```text
uv run pytest -q -n0 pwa_tests/integration/test_content_assets_smoke.py \
  -k 'raster_corpus or public_math_photo or strips_exif'
5 passed, 1 deselected in 12.71s
```

После добавления corpus полный PWA Python gate в восьми изолированных workers:
`1551 passed, 5 intentional skips` за `80.63s`.

Локальный toolchain:

- ImageMagick `7.1.2-27`, delegates `heic`, `jpeg`, `webp`;
- libheif `1.23.1`;
- cwebp/libwebp `1.6.0`;
- ExifTool используется только тестом для создания и повторной проверки EXIF,
  production pipeline от него не зависит.

Общий TikZ → SVG и raster → WebP smoke остаётся в том же integration-файле и
ранее подтверждён отчётом
[`phase11-live-adapters-2026-07-30.md`](phase11-live-adapters-2026-07-30.md).

## Граница доказательства

Это локальный corpus gate server fallback. Browser-side HEIC поддерживается
только там, где конкретный browser decoder умеет его прочитать; иначе исходный
HEIC остаётся во временном локальном outbox до отправки на этот проверенный
server fallback. Production service-profile readiness и Hetzner S3 остаются
Phase-11 gates.
