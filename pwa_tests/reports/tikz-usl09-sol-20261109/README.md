# Диагностика usl-09-x-sol.tex — 9 ноября 2026

Причина двух отказов загрузки на ВМШ — `\pdfrender` в `labelstyle`
рисунка с льдинками. Правило `_FORBIDDEN_TEX_PRIMITIVE` в
[`assets.py`](../../../helpers/pwa/content/assets.py) отклоняет команды
с префиксом `\pdf` до запуска LaTeX. Обработка останавливается на первом
ошибочном asset в
[`_resolve_reusable_revision_assets`](../../../apps/pwa_api/content_routes.py).
Это объясняет частично обработанные картинки.

Read-only проверка журнала и двух исходников в production SQLite:

| Revision | Загрузка, UTC | Source SHA-256 |
| --- | --- | --- |
| cr-183 | 2026-11-08 23:57:11 | `85f471a308205c5da6d304d886753c7d90710bdd185250d30224d4e6fecefe4c` |
| cr-184 | 2026-11-09 00:02:33 | `8497f401db93fdd831397011ca507e20b67e7e1459fcff2f214814cc7b60caff` |

Оба отказа: `asset=tikz-04c2412f716c0ad3`,
`reason=asset.tikz_forbidden_command`, `capability=latex-to-pdf`.
В обоих сохранённых исходниках присутствует
`\pdfrender{TextRenderingMode=FillStroke,LineWidth=0.3pt}`.

Текущий файл Dropbox отличается от обеих загрузок:
SHA-256 `c7736fec1235cbe97bd8b187c24bcad3709464ee17118297bc27373dff82c4d6`.
На строке 218 уже используется `\large\sffamily\fontseries{bx}\selectfont`;
`\pdfrender` отсутствует. Windows-1251 распознан штатным compiler,
12 задач разобраны без diagnostics. Все 7 TikZ-блоков прошли настоящую
конвертацию `pdflatex → pdf2svg` локально и на текущем ВМШ (commit `7ee70914`):

| Строка обёртки | Серверный SVG, размеры | Bytes |
| --- | --- | --- |
| 86 | 294 × 67 | 4881 |
| 213 | 148 × 148 | 7578 |
| 246 | 289 × 148 | 13069 |
| 322 | 289 × 148 | 13825 |
| 414 | 97 × 111 | 1648 |
| 431 | 97 × 111 | 2628 |
| 598 | 146 × 202 | 18524 |

Серверный probe использовал текущий source из памяти и автоматически
удаляемые временные файлы под `/web/vmsh_tasks_bot/vmshpwa/runtime`.
БД, опубликованные материалы, код и службы не изменялись.
Исправлять текущий TeX для этой ошибки не требуется: нужно загрузить его
новую версию вместо сохранённых cr-183/cr-184. Повторная загрузка и публикация
в рамках диагностики не выполнялись. Общий PWA gate не запускался:
изменены только этот отчёт и STATUS.

## Исправление валидации

По последующему разрешению владельца изменён
[`assets.py`](../../../helpers/pwa/content/assets.py): вместо запрета всех
команд с префиксами `pdf`, `file`, `sys`, `luatex` проверяются конкретные
файловые и execution-операции. Комментарии исключены из проверок команд и
границ документа, с сохранением обработки экранированного процента.
Уточнена граница имени команды: `\openin1` тоже отклоняется.
В фиксированную преамбулу включён пакет `pdfrender` для `\pdfrender` и
`\textpdfrender`. Runtime argv, файловые ограничения, timeout и лимиты
размеров сохранены. Фильтр не объявляется песочницей ОС.

Профильные тесты:

```sh
PATH=/Library/TeX/texbin:$PATH VMSH_PDFLATEX_PATH=/Library/TeX/texbin/pdflatex \
  /Users/sergeyshashkov/repos/vmsh_tasks_bot/.venv/bin/python -m pytest -q -n0 \
  pwa_tests/domain/test_content_tikz.py \
  pwa_tests/domain/test_content_assets.py \
  pwa_tests/integration/test_content_assets_smoke.py \
  -k 'not real_raster_corpus and not real_raster_rejects and not real_jpeg'
```

Итог: **60 PASS / 1 SKIP / 3 deselected**. Skip — отсутствующий внешний
фото-корпус; три raster-corpus tests не относятся к TikZ. Реальный regression
test проверяет наличие обводки около 0.3pt в SVG, а не только успешный exit.
Все 7 рисунков текущего source отдельно прошли изменённый converter.
Дополнительно во втором рисунке в памяти восстановлен прежний стиль
`\bfseries\pdfrender{TextRenderingMode=FillStroke,LineWidth=0.3pt}`:
конвертация PASS, 148 × 148, 13710 bytes; обводка присутствует в SVG.
Полные cr-183/cr-184 повторно не проверены: попытка read-only SSH retrieval
вернула `Permission denied (publickey,password)`. Сами версии не изменялись.

Обязательный `make pwa-check-fast PWA_E2E_MODES=content` запущен с существующим
Python environment, но остановлен до тестов: в текущем checkout отсутствует
`vmshpwa/node_modules`. Receipt:
`.runtime/vmshpwa/checks/20261109T101207.017319Z/summary.json`.
Предыдущие исправленные падения профильного запуска: граница `\openin1`,
различие SVG styles/attributes в версиях pdf2svg; локальный TeX PATH и
последовательный запуск устранили missing mktextfm и timeout при n8.
`git diff --check` PASS. Временный пустой test config удалён после тестов.
Production code/config/DB/services не менялись, публикация не выполнялась.

## Выпуск на оба production

Владелец разрешил commit/push и выпуск на ВМШ Timeweb и TLF.
Начат backend-only rollout с online backups и плавной заменой workers;
серверные локальные исправления метаданных, config/schema/static/NATS сохраняются.
Source до выпуска на обоих: `7ee709141deddbf624d3034a9d092ef02e4bb2e2`.
Исходный общий fast gate ограничен отсутствием frontend dependencies;
профильные проверки выше приняты владельцем при разрешении выпуска.
