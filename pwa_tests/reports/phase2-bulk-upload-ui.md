# Phase 2 — пакетная загрузка материалов в Staff

Дата: 28 июля 2026 года.

## Результат

Staff получил рабочий пакетный сценарий для LaTeX-материалов одного занятия
курса. Администратор выбирает до 100 файлов и для каждого явно указывает
конкретное групповое занятие и вид материала: условие, подсказку или решение.
Имя файла не участвует в определении группы либо вида материала.

Сценарий переиспользует существующие одиночные authenticated операции
upload/compile. Готовые revisions сохраняются независимо от ошибок соседних
файлов и не публикуются автоматически.

## Реализация

- `BulkContentUpload` получает только targets того же `course_lesson` через
  `useContentUploadTargetsQuery`.
- Каждая строка имеет явные group/material controls, мягкий цветовой marker
  группы, размер файла, фазу и собственный diagnostic.
- Archived target недоступен; пустой, не-`.tex`, больший 512 КиБ файл,
  незаполненная строка и повтор `(groupLessonId, kind)` блокируют запуск.
- До 100 небольших weekly-файлов обрабатываются последовательно: это сохраняет
  ясный per-file progress и не создаёт параллельный пик TeX/PDF subprocesses.
- Ошибка одного файла даёт partial result, не откатывая уже готовые revisions.
  Ошибка итогового refetch не искажает результат обработки и предлагает
  обновить страницу.
- Кнопка и поясняющий текст явно фиксируют: загрузка и compile не являются
  публикацией.

Реализующие файлы:

- `vmshpwa/apps/staff/src/bulk-content-upload.tsx`;
- `vmshpwa/apps/staff/src/bulk-content-upload-model.ts`;
- `vmshpwa/apps/staff/src/content-page.tsx`;
- `vmshpwa/apps/staff/src/content-page.stories.tsx`.

## Storybook

Story ID:

`pages-staff-content-publication--bulk-upload-explicit-mapping`

Interaction загружает два synthetic `.tex`, явно выбирает разные группы и
`condition`, затем получает одну готовую revision и один missing-asset
diagnostic. Проверяются понятные выбранные labels вместо внутренних ID, partial
summary и отсутствие автоматической публикации.

Mobile light 390×844 и desktop light 1280×720 просмотрены вручную на agent
Storybook `:6106`. Горизонтального переполнения нет; строки складываются в
карточки на mobile и остаются плотными строками на desktop. Snapshots не
обновлялись.

## Проверки

```text
Prettier affected files
PASS

strict TypeScript: Staff
PASS

ESLint affected Staff files
PASS

Vitest: bulk model + content contracts/client
25 passed

Storybook browser mode: content-page.stories.tsx
12 passed; addon-a11y remains error-level

Staff production build: route generation + Vite build
PASS
```

## Что остаётся открытым

Production-build Playwright должен связать настоящий aiohttp и SQLite с
production bundles во всех трёх браузерах: Staff upload/compile/matching/
metadata/publish, Student read и rollback. Owner visual approval и snapshots
по-прежнему отдельный gate.
