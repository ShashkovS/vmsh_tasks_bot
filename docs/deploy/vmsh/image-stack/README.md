# HEIC/HEIF → WebP: рабочая сборка

На production используется **только**
`/opt/vmsh-image-stack/current/bin/magick`, сейчас `current → 20261117`.
Системный `/usr/bin/magick` не является конвертером приложения.

| Компонент | Проверенная версия | Исходник |
|---|---|---|
| ImageMagick | 7.1.2-36 Q16-HDRI | [release](https://github.com/ImageMagick/ImageMagick/releases/tag/7.1.2-36) |
| libheif | 1.23.7 | [release](https://github.com/strukturag/libheif/releases/tag/v1.23.7) |
| libde265 | 1.1.3 | [release](https://github.com/strukturag/libde265/releases/tag/v1.1.3) |
| FFmpeg (HEVC decoder) | 9.0.2 | [исходники](https://github.com/FFmpeg/FFmpeg/tree/n9.0.2) |
| UltraHDR | 2.0.2 | [release](https://github.com/google/libultrahdr/releases/tag/v2.0.2) |

Остальные delegates (JPEG/PNG/WebP/JXL/RAW и др.) — dev-пакеты подписанных
репозиториев Ubuntu. Свежие libheif/libde265/FFmpeg/UltraHDR собраны вместе с IM.
HEVC-декодеры встроены в libheif, загрузка внешних HEIF plugins отключена.

## Установка на чистом Ubuntu 26.04

```bash
sudo bash docs/deploy/vmsh/image-stack/build.sh
```

Рецепт фиксирует версии/SHA-256, собирает в два потока, устанавливает в отдельный
`/opt` prefix. Логи/исходники — `/web/vmsh_tasks_bot/image-stack`.
На работающем VPS запускать с `nice` и оставить CPU для приложения.
Обычная установка зависимостей не должна упираться в недоступный Grafana repo:
скрипт обновляет только подписанные Ubuntu sources.

RPATH каждой собственной библиотеки указывает на тот же prefix. Глобальные
`LD_LIBRARY_PATH` и `/etc/ld.so.conf.d` менять не нужно. Проверка:

```bash
PREFIX=/opt/vmsh-image-stack/20261117
"$PREFIX/bin/magick" -version
ldd "$PREFIX/lib/libMagickCore-7.Q16HDRI.so.10" | grep -E 'heif|de265|avcodec|avutil|uhdr'
```

В выводе HEIF/HEVC/UltraHDR должны загружаться из этого prefix, а не из `/usr/lib`.
Системная `policy.xml` переносится в новую сборку; лимиты конвертации остаются
в приложении. Не отключать policy ради успешного smoke-теста.

После проверки создать/переключить `current` symlink. В
`vmshpwa/runtime/vmshpwa.env`:

```text
VMSH_MAGICK_PATH=/opt/vmsh-image-stack/current/bin/magick
```

В production JSON legacy-адаптера — `magick_path` с тем же абсолютным путём.
`/usr/local/bin/{magick,convert,identify}` указывают на новые executables для CLI;
прочие команды из prefix массово в `/usr/local/bin` не линковать.
Перезапустить `vmshpwa` и `gunicorn.vmsh_tasks_bot`, проверить `/service-status`.
При обновлении версий сначала собрать **другой prefix**, проверить, затем
переключить symlink. `apt upgrade` эту собственную сборку не обновляет.

## Как конвертирует приложение

[ContentAssetConverter.raster_to_webp](../../../../helpers/pwa/content/assets.py)
вызывает ImageMagick один раз:

```bash
"$PREFIX/bin/magick" -limit memory 256MiB -limit map 512MiB -limit disk 1GiB \
  'input.heic[0]' -auto-orient -strip -resize '1920x1920>' -quality 82 output.webp
```

Берётся основное/первое изображение. Автоориентация выполняется до удаления
метаданных, большая сторона ограничена 1920 px. JPEG/PNG/WebP проходят тот же
путь. **Промежуточного PNG и вызова `cwebp` нет.** Сохраняются проверка размера,
геометрии WebP, SHA-256, таймауты и серверная диагностика ошибок; source bytes и
секреты в сообщения клиенту не попадают. SVG/PDF/TikZ сохраняют собственные
конвертеры, это изменение относится к растровым фотографиям.

## Что считать проверкой

PNG → WebP не проверяет HEIC. Нужны реальные HEIC/HEIF, включая 10/12 бит,
прозрачность, ориентацию и современный телефон. Также JPEG с EXIF GPS,
PNG/WebP и отказ на испорченном файле. Открыть/декодировать результат независимым
`dwebp`; убедиться, что EXIF/комментариев не осталось.

17 ноября проверен реальный метод приложения на **12 образцах**, из них
8 HEIC/HEIF из публичного [pillow-heif corpus](corpus-sources.json).
Все 8 старый системный IM 7.1.2-18 обработать не смог, новая сборка обработала
все 8, включая spatial photo и Xiaomi. Остальные 4 — JPEG (в том числе GPS),
PNG и WebP. [Результаты](proof.json). Unit-тесты прямого пути: 19 passed,
[test_content_assets.py](../../../../pwa_tests/domain/test_content_assets.py).

[qa.py](qa.py) — изолированная проверка staging-кандидата, без записей в БД/S3.
[stage_direct_webp.py](stage_direct_webp.py) и [activate.py](activate.py) —
одноразовые инструменты этого обновления с проверками конкретной версии
production-кода. На следующем сервере брать уже исправленный код из Git/patch,
а не повторно запускать эти патчи.

Исходники семи пользовательских неудачных загрузок в этом прогоне не были
доступны: их повторная загрузка — отдельная проверка конкретных файлов.

## Что хранить

В Git — рецепт, версии, тесты и небольшой отчёт. В компактном бэкапе — env/JSON
с выбранным путём, source patch и маленький рецепт/checksums в
`backup-local-changes`. **Ни `/opt` с бинарниками, ни build/src, ни QA-картинки
в бэкап не включать.** После успешной установки `image-stack/src` можно удалить:
все runtime-библиотеки установлены в prefix.
