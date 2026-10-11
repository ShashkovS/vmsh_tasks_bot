# Простыня: одно сообщение в переписке — 11 октября 2026

Замечание владельца: показывать решение повторно в блоке «Материалы оценки»
не нужно. [Решение](../../../vmshpwa/docs/review-sheet.md#11-октября--единая-переписка-без-повторов).

[ReviewSheetCard](../../../vmshpwa/apps/staff/src/review-sheet-card.tsx) встраивает
[ReviewEvidenceEntry](../../../vmshpwa/apps/staff/src/review-workspace-page.tsx)
в сообщение общей истории по стабильному public entry ID. Одно отображение текста
и фотографии, перенос/клонирование/разметка на том же сообщении. Старые ответы и
результаты сохраняются, evidence/CAS не расширяются. Текущая работа сразу доступна
при подгрузке истории; ключ сообщения и открытый редактор сохраняются после
загрузки соответствующего архивного события. Отдельный повторный блок удалён.

Регрессии: [Staff pagination/dedup test](../../../vmshpwa/apps/staff/src/review-sheet-page.test.tsx),
[HTTP public entry mapping](../../integration/test_review_sheet_http.py),
[браузерный Sheet scenario](../../../vmshpwa/e2e/review-workspace.spec.ts).

`make pwa-check-fast PWA_E2E_MODES="review submissions student-results"`: PASS.
2981 Python / 12 SKIP, 1102 frontend, 375 Storybook, 10 Chromium E2E PASS;
format/types/lint/i18n/build PASS. [Gate](fast-summary.json), [E2E](fast-e2e.json).
Source digest `9b82f1d1bae1f5e1aca23b6607d5395009688411062c0f16bc33f8f2a315b83d`,
`source_changed=false`. Общие ограничения прежнего полного release gate не
перепроверялись этим малым прогоном и не объявляются устранёнными.

Снимки review-фазы очищены следующей student-results фазой runner. Для их
сохранения выполнен отдельно тот же review mode/Chromium: 4/4 PASS, без изменения
исходников ([квитанция](visual-e2e.json)). Сохранены 6 [снимков](screenshots);
просмотрены карточка конфликта light и 390 px dark. Дубля нет, разметка и
действия при решении сохранены, форма и мобильный экран помещаются.
Выпуск исправления начат в ранее авторизованном владельцем scope фичи.
