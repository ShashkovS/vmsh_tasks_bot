# Очередь проверки: сводка, фильтры и ожидание

Реализация требований [серийной проверки](serial-review.md#понятная-очередь-и-фильтры):
`apps/staff/src/review-queue-page.tsx`, `review-queue-model.ts`, родительский маршрут
`routes/review.tsx`. Общее число — уникальные работы, а не сумма карточек синонимов.
Переходы в одиночную/серийную проверку и назад сохраняют параметры очереди.

## Проверки

- `pnpm exec vitest run --project unit apps/staff/src/review-queue-model.test.ts apps/staff/src/review-series-model.test.ts`: 22 теста прошли. Свои/чужие захваты, дедупликация, проекция веток без изменения claim identity, фильтры, сортировки, склонения, дни/часы, URL.
- `pnpm exec vitest run --config vitest.storybook.config.ts packages/product/src/review.stories.tsx --testNamePattern 'Очередь'`: 2 stories прошли в Chromium, включая отсутствие встроенной сводки.
- `pnpm typecheck`, сборка всех приложений и ESLint изменённых файлов прошли.
- `e2e/review-queue.spec.ts` использует реальные логины учителя и администратора, API и realtime, без MSW. Проверяет, что фильтры не вызывают mutations, занятие работы коллегой меняет счётчики и блокирует кнопку, отказ возвращает доступность, параметры восстанавливаются после reload и обоих способов проверки.
- Совместный прогон `e2e/review-queue.spec.ts e2e/review-workspace.spec.ts`: **9 passed**, Chromium, WebKit и Firefox.
- `e2e/review-workspace.spec.ts` сохраняет регрессии вердикта, черновика, аннотаций, синонимичных переносов и последовательной проверки. URL-ожидания учитывают сохранённые параметры очереди.

Все E2E выполняются под `exclusive_e2e_run` с отдельной сбрасываемой базой и gateway; production и человеческий runtime не используются.

## Снимки

Синтетические работы; даты в сценарии ожидания зафиксированы для проверки минутного обновления.

| Браузер  | Desktop                                            | 320 px, тёмная тема                            | 390 px, светлая тема                           | 200%                                            |
| -------- | -------------------------------------------------- | ---------------------------------------------- | ---------------------------------------------- | ----------------------------------------------- |
| Chromium | [снимок](assets/review-queue/chromium-desktop.png) | [снимок](assets/review-queue/chromium-320.png) | [снимок](assets/review-queue/chromium-390.png) | [снимок](assets/review-queue/chromium-zoom.png) |
| WebKit   | [снимок](assets/review-queue/webkit-desktop.png)   | [снимок](assets/review-queue/webkit-320.png)   | [снимок](assets/review-queue/webkit-390.png)   | [снимок](assets/review-queue/webkit-zoom.png)   |
| Firefox  | [снимок](assets/review-queue/firefox-desktop.png)  | [снимок](assets/review-queue/firefox-320.png)  | [снимок](assets/review-queue/firefox-390.png)  | [снимок](assets/review-queue/firefox-zoom.png)  |

На визуальном просмотре исправлены контраст отключённой кнопки-ссылки и минимальная высота нативных селекторов WebKit. Финальный прогон: **3 passed** в Chromium/WebKit/Firefox. Проверены размер controls (не менее 32 CSS px), обе темы, клавиатура, 320/390 px, отсутствие горизонтального переполнения страницы и CSS zoom 200%. Снимки просмотрены; подписи и действия помещаются. CSS zoom проверяет масштабирование содержимого, а не системный диалог браузера. Повторный Staff typecheck, ESLint, Prettier и diff-check прошли. Миграций и изменений API нет; выпуск на production не выполнялся.
