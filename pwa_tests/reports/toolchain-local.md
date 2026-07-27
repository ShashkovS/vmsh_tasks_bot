# Локальная проверка converter toolchain

Дата: 27 июля 2026 года. Профиль: `pwa-agent`. Среда: macOS arm64. Проверка не использовала сеть, credentials или пользовательские данные; все файлы создавались во временном каталоге и были удалены автоматически.

## Capability/version preflight

- `pdf2svg`: executable запускается; программа не предоставляет переносимого version-флага и в ответ на пустой argv печатает usage;
- `cwebp`: `1.6.0`;
- `pdflatex`: `MiKTeX-pdfTeX 4.10 (MiKTeX 22.1)`;
- `magick`: `ImageMagick 7.1.2-27`, сборка `20260705`;
- абсолютный локальный override `pdflatex` был передан через environment и не сохранён в отчёте.

MiKTeX хранит служебное состояние вне рабочего дерева. Поэтому запуск из
ограниченного filesystem sandbox может корректно закончиться timeout даже при
рабочем executable; приведённый ниже proof получен с разрешённым доступом
MiKTeX к собственным локальным каталогам, но без сетевого доступа и без доступа
к production credentials.

## Поведенческий smoke

- synthetic TikZ с числом 179 успешно прошёл `pdflatex -no-shell-escape → pdf2svg`;
- PDF: 10 737 bytes; SVG: 3 486 bytes;
- synthetic PPM успешно прошёл `magick -auto-orient → PNG → cwebp -resize 1920 0 -q 82`;
- WebP: 8 092 bytes;
- ImageMagick format listing заявляет HEIC/HEIF decode capability.

Хеши производных формируются командой и могут использоваться для диагностики одного запуска, но не являются cross-machine golden: LaTeX/tool metadata способны изменяться между версиями. Автоматические fake-tool tests проверяют fixed argv, shell-injection boundary, timeout с остановкой process group, ограничение stdout/stderr, missing/disabled/non-zero состояния и отсутствие абсолютного пути в публичном отчёте.

Это доказательство локальной готовности developer toolchain, а не production/staging gate. Тот же smoke должен быть повторён под service account при rollout Phase 11.
