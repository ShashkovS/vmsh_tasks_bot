# Превью подсказок и отсутствие материала — 2026-10-04

Владелец требует на `/staff/lessons/gl-14` тот же просмотр и редактор рисунков
для подсказок, что для решений: текст, размер, расположение, скрытие/восстановление.
Отсутствие подсказки или обоих разделов ответа/решения в конкретной задаче
(и самостоятельном пункте) нормально: Student и Staff preview не показывают
соответствующую кнопку. Наличие только ответа достаточно для решения.

Readonly осмотр подтвердил ready hint cr-79/compiler 9; карточка скрывает ready
selector/preview из-за `missingAssets`, вычисленных по всему canonical AST,
включая исключённые рисунки решения. Общий `MaterialWorkflowCard` уже использует
тот же `StaffWorksheetPreview` и `FigureLayoutEditor` для hints/solutions.
Исправление должно охватить HTTP payload, а не только визуальный обход проверки.

Реализация: роль и наличие материала учитываются единым pure helper
`helpers/pwa/content/material_selection.py` в inventory/compiler/read projection.
`apps/pwa_api/content_routes.py` выдаёт missingAssets только выбранного материала.
Wire metadata наличия материала/пунктов совместима со старыми derivatives;
readonly overlay по canonical source применяется также к старым публикациям.
`db_methods/pwa/content.py` исключает пустое из availability и запрещает reveal
до записи audit. `StaffWorksheetPreview` использует тот же renderer/editor для
обоих видов материала и проверяет содержимое выбранного пункта. Schema/старые
revisions, публикации, результаты и пользовательские drafts не переписываются.

Проверки: source role projection, HTTP upload → preview → layout save → publish,
Student availability/reveal (без фиктивного события), old publication compatibility,
frontend unit/Storybook и реальный Chromium flow с редактированием подсказки,
reload, публикацией и отсутствующими разделами. Затем общий fast gate
`content figure-layout`, i18n extraction новых сообщений и guarded выпуск обоих
порталов по уже данному разрешению владельца. Старый Large Classroom performance
blocker фиксируется отдельно, если повторится. Production учебные материалы
агент не публикует: UI smoke readonly, содержательные проверки — изолированные.

## Состояние

Реализовано; 2839 Python / 7 SKIP, 1032 frontend, 356 Storybook, 6 Chromium cases
прошли. Старые derivatives покрыты read-only source overlay. После исправления
ожидания auto-match повторён только figure-layout E2E (4 PASS).
[Точный отчёт, receipts, preview и guarded release](../../pwa_tests/reports/hint-preview-empty-materials-20261004/README.md).
Выпущен `cc60df33` на ВМШ webhook и ручным TLF script по разрешению владельца.
Readonly smoke gl-14 подтвердил ready v7, текст подсказок и инструменты всех
четырёх рисунков. Учебные публикации не менялись. На TLF все 158 product tables
и 23862 строки идентичны, включая 1593 raw Zoom receipts; по 25 public HTTP PASS.
[Production proof](../../pwa_tests/reports/hint-preview-empty-materials-20261004/production-proof.json).
