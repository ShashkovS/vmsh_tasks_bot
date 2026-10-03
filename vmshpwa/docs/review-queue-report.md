# Очередь проверки: сводка, фильтры и ожидание

Реализация требований [серийной проверки](serial-review.md#понятная-очередь-и-фильтры):
`apps/staff/src/review-queue-page.tsx`, `review-queue-model.ts`, родительский маршрут
`routes/review.tsx`. Общее число — уникальные работы, а не сумма карточек синонимов.
Переходы в одиночную/серийную проверку и назад сохраняют параметры очереди.

## Исправление счётчиков — 3 октября 2026

Причина: frontend считал и дедуплицировал по `logicalCaseId`, который сервер
возвращает как ID задачи/группы синонимов. У разных учеников он совпадает:
80 решений одной задачи превращались в одну «работу», а одна занятая работа
могла скрыть доступные решения остальных учеников. Главная сводка Staff считает
серверные случаи напрямую и не содержит этой ошибки
([`staff_dashboard_routes.py`](../../apps/pwa_api/staff_dashboard_routes.py)).

Исправление в [`review-queue-model.ts`](../apps/staff/src/review-queue-model.ts)
и [`review-series-model.ts`](../apps/staff/src/review-series-model.ts):
дедупликация и группировка используют исходный `queueId`, общий для всех
синонимичных веток одного ученика и отдельный для каждой работы.
[`review-series-page.tsx`](../apps/staff/src/review-series-page.tsx) использует
тот же ключ при исключении проверенных, пропущенных и подготовленных работ.
Сводка «Ждут проверки»/«Можно проверить»/«У других преподавателей», карточки
задач, сортировка «Больше работ» и таблица теперь учитывают все решения.
Фильтр сохраняет исходный ключ даже при скрытии первой ветки; синонимы одной
работы не удваивают сводку. Семантика wire-поля документирована в
[`review-queue.ts`](../packages/contracts/src/review-queue.ts).

Регрессии в [`review-queue-model.test.ts`](../apps/staff/src/review-queue-model.test.ts)
воспроизводят 80 решений одной задачи, одинаковые `logicalCaseId`, отсутствующие
legacy public ID учеников, синонимы и свои/чужие захваты.
[`review-queue-page.test.tsx`](../apps/staff/src/review-queue-page.test.tsx)
проверяет видимые числа для 52 решений из двух страниц API: 52 ждут, 51 доступно,
1 у коллеги; карточку задачи, таблицу, фильтр и отсутствие лишнего захвата.
[`review-series-model.test.ts`](../apps/staff/src/review-series-model.test.ts)
и [`review-series-page.test.tsx`](../apps/staff/src/review-series-page.test.tsx)
проверяют группировку синонимов и продолжение серии для других учеников после
сохранения/пропуска. До исправления 7 модельных проверок падали на неверном
подсчёте и выборе работ; после исправления 49 focused unit/contract/client tests
прошли.

Проверки этого исправления:

- `./node_modules/.bin/vitest run --project unit apps/staff/src/review-queue-model.test.ts apps/staff/src/review-queue-page.test.tsx apps/staff/src/review-series-model.test.ts apps/staff/src/review-series-page.test.tsx packages/contracts/src/review-queue.test.ts packages/app-shell/src/review-queue-client.test.ts` — **49 passed**, 6 файлов.
- `./node_modules/.bin/tsc --noEmit -p apps/staff/tsconfig.json`, затем `packages/contracts/tsconfig.json` и `tsconfig.json` — проходят.
- Scoped ESLint `--max-warnings=0`, Prettier изменённых TS/TSX и `git diff --check` — проходят.
- `make pwa-typecheck` остановлен после зависания на запуске `pnpm`; проверки выполнены установленными workspace binaries (Node 26.9.0).
- Первый Staff production build: `run_commands((("node_modules/.bin/vite", "build", "apps/staff"),))` под `exclusive_e2e_run` — был заблокирован `vmsh:i18n-catalog-coverage-guard`: 3 сообщения отсутствуют в каталогах для параллельно изменённого `apps/staff/src/problem-review-workflow.tsx`. При исправлении счётчиков эти изменения и каталоги были сохранены без правок. Новых пользовательских строк исправление счётчиков не добавляет.

По следующему запросу владельца 3 октября добавлены недостающие переводы
metadata reload в [`Staff en.po`](../apps/staff/src/locales/en.po):
«Loading from the server…», «Discard draft and load from the server»,
«Could not load the table from the server». Source
[`ru.po`](../apps/staff/src/locales/ru.po) обновлён извлечением Lingui.

- `./node_modules/.bin/lingui extract --clean` — успешно.
- `node scripts/i18n-check.mjs --no-extract` — успешно: English coverage и слияние всех app catalogs.
- `.venv/bin/python -m vmshpwa.scripts.backend_i18n check` из корня — успешно.
- Повторный Staff build той же командой под `exclusive_e2e_run` — успешно; Lingui blocker снят. Остаётся штатное предупреждение Vite о крупных chunks.

Изменения API и миграции для счётчиков/переводов не требуются. В общем выпуске
3 октября полные frontend unit tests прошли (1021), а очередь и workspace
проверены на настоящем backend во всех трёх браузерах (9 сценариев).
Все 12 снимков ниже обновлены и просмотрены: карточки с двумя решениями
учитываются в общей сводке, чужой захват уменьшает доступное число на один.
Исправление и переводы выпущены 3 октября на ВМШ/TLF в `26e2f7ee`.
Состояние production и общий gate описаны в
[протоколе выпуска](../../pwa_tests/reports/release-20261003/README.md).

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
