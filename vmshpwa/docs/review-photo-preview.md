# Просмотр и копирование фотографий решений

Решение владельца, 11 октября 2026: преподавателю нужны оригинал в новой
вкладке и раскрытие фотографии на всё окно с увеличением/уменьшением.
Пометки остаются в обычном режиме проверки. Наличие комментария не влияет
на возможность скопировать фото через стандартное меню браузера.

## Поведение

- Исходный сохранённый файл в полном разрешении открывается защищённой ссылкой
  «Открыть оригинал» в новой вкладке, без зависимости от Blob URL текущей работы.
- Начальный режим — просмотр: клик по фото раскрывает его на всё окно.
  Выбор инструмента включает рисование; «Просмотр» возвращает обычный просмотр.
  Кнопка «На весь экран» доступна и при рисовании.
- Полноэкранное окно вписывает фото целиком, поддерживает масштаб 25–400%
  относительно вписанного размера, прокрутку обеих осей, Escape и возврат фокуса.
- Просмотр показывает текущие пометки/поворот, но не изменяет черновик или историю.
  Правая кнопка получает само изображение; копируется фото без SVG-пометок.
- Оригинал — файл, сохранённый системой, включая прежнее преобразование в WebP.

## Реализация

- [ReviewPhotoPreview](../packages/product/src/review-photo-preview.tsx): общие
  действия и диалог; [ReviewAnnotationSurface](../packages/product/src/review-annotation-surface.tsx)
  сохраняет [совместимую геометрию](review-annotation-geometry.md).
- [ReviewAnnotationViewer](../packages/product/src/review-annotation-viewer.tsx):
  тот же просмотр сохранённых пометок; все компоненты экспортируются из `@vmsh/product`.
- [ReviewAnnotationEditor](../packages/product/src/review-annotation-editor.tsx):
  просмотр/рисование и неизменность черновика.
- [ReviewAttachmentImage](../apps/staff/src/review-workspace-page.tsx) и
  [ArchiveImage](../apps/staff/src/student-results-history.tsx): текущие фото,
  история и переписка. [WrittenMaterialReassignmentClient](../packages/app-shell/src/written-material-reassignment-client.ts)
  предоставляет `attachmentMediaUrl(entryId, attachmentId)` для URL
  существующего authorized media endpoint; маршруты, контракты и БД не меняются.
- [Storybook](../packages/product/src/review-annotation.stories.tsx) и
  [E2E](../e2e/review-workspace.spec.ts) проверяют просмотр и обычную проверку.

## Проверка

`make pwa-check-release PWA_E2E_MODES="review submissions"` — PASS:
2955 Python / 12 SKIP, 1091 frontend, 373 Storybook, 18 E2E в Chromium/WebKit/Firefox.
Типы, format, JS/CSS lint и i18n PASS; source unchanged.
[Отчёт и 21 осмотренный снимок](../../pwa_tests/reports/review-photo-preview-20261011/README.md).

Firefox выявил повреждённый прежний 1px WebP в E2E seed.
[Seed](../scripts/seed_e2e_review.py) теперь использует существующее синтетическое
фото 640×360. Серверные заголовки, авторизация и API сохраняются.

Системное меню «Копировать изображение» и вставка во внешний редактор требуют
ручной проверки: native apps недоступны из-за заблокированного Mac. E2E проверяет
попадание мыши в img, незаблокированный contextmenu и выдачу исходного файла.
