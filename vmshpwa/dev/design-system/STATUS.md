# Design-system status

Этот файл — журнал gates. Визуальная модель обновляет evidence и вопросы, но ставит `accepted` только после явного решения владельца продукта.

| Фаза                     | Статус             | Принято | Evidence/решение                                                             |
| ------------------------ | ------------------ | ------- | ---------------------------------------------------------------------------- |
| 1. Art direction         | ready for review   | —       | A/B/C; знак B выбран baseline, финальное сравнение языка ещё не принято.     |
| 2. Brand and tokens      | blocked by phase 1 | —       | —                                                                            |
| 3. UI primitives         | blocked by phase 2 | —       | Технические placeholders не считаются принятой фазой.                        |
| 4. Product components    | blocked by phase 3 | —       | —                                                                            |
| 5. Pages and flows       | blocked by phase 4 | —       | Существующие prototype pages — content skeletons, не принятый visual design. |
| 6. Storybook and testing | blocked by phase 5 | —       | Текущая Storybook-конфигурация — инфраструктурный фундамент.                 |
| 7. Final acceptance      | blocked            | —       | —                                                                            |

Допустимые статусы: `not started`, `in progress`, `ready for review`, `changes requested`, `accepted`, `blocked by phase N`.

## Журнал решений

Добавлять запись в формате:

```text
YYYY-MM-DD — Phase N — accepted/changes requested
Decision owner:
Chosen option and exact combination:
Rejected traits:
Evidence stories:
Known follow-ups:
```

## Фаза 1 — материалы на рассмотрение (решение владельца не принято)

Stories: `Exploration/Art direction` — «A · Листок», «B · Мастерская», «C · Архив»,
каждая в светлой и тёмной теме, плюс «Сравнение A / B / C». Глобальные переключатели
Storybook: тема, плотность (Школьник / Семья / Учитель), анимация.

Содержание всех трёх направлений одинаково и взято из реальных материалов кружка:
листок 21н (задачи 21н.1, 21н.4, 21н.6, 21н.7, 21н.8), задачи 27х.1 и 27х.3 с формулами
и таблицей, пост канала за 26 января.

Проверки на момент подготовки: `pwa-format`, `pwa-lint`, `pwa-typecheck`, `pwa-test`,
`pwa-storybook-test` (16/16, addon-a11y в режиме `error`), `pwa-build`.
Контраст: `node dev/design-system/exploration/contrast-audit.mjs` — 156 пар × 3 направления
× 2 темы проходят WCAG 2.2 AA (текст 4.5:1, границы и focus 3:1).

Исправлено по ходу фазы 1 (инфраструктура, не визуальное решение):

- Storybook не рендерил ни одной story: отсутствовал `mockServiceWorker.js` и `staticDirs`;
- добавлены глобальные переключатели плотности и reduced motion;
- `dev/**` включён в `tsconfig.json`, иначе ESLint не мог разобрать файлы фазы 1.

Решения, принятые владельцем до реализации:

- шрифты: self-host двух OFL-семейств (UI sans + reading serif), кириллический subset,
  precache; кандидаты подключены как `@fontsource*` devDependencies и живут только в Storybook;
- уровни: три именованных семейства + нейтральный fallback, цвет назначается по `groups.sort_order`;
- статистика сложности задачи показывается школьнику только после завершения проверки
  всего занятия — по явному разрешению или через фиксированные семь дней после закрытия приёма;
- KaTeX рендерится на клиенте; math fonts входят в PWA precache, TikZ остаётся external SVG;
- Sonner заменяется Base UI Toast, Sheet — Base UI Drawer;
- графики используют Visx/D3, Staff grid — TanStack Table/Virtual, новая DnD dependency не добавляется;
- a11y baseline и axe gate сохраняются для Staff; упрощение DnD не создаёт исключения;
- Playwright E2E/visual запускаются на production bundles через Vite preview;
- brand baseline: знак B — скруглённый прямоугольник `179` с антенной, его палитра и простой sans wordmark; антенна сохраняется на 16 px после отдельной проверки читаемости;
- verdict UI строится из registry курса и поддерживает binary/ternary/full scale; тип, lock/review, reactions, hint/solution и future AI states заданы в `docs/product-ux-decisions-2026-07.md`;
- подробный реестр остальных решений: `docs/accepted-technical-decisions-2026-07.md`.

## Следующий gate

Следующий шаг — не Phase 2 и не расширение набора компонентов. Сначала Claude должен обновить финальное Phase 1 comparison так, чтобы во всех A/B/C использовался уже выбранный знак B, а различались только typography, surfaces, spacing/density, layout grouping и level-color logic. Затем владелец одним явным решением фиксирует:

1. основное направление A, B или C;
2. точные заимствования из остальных вариантов;
3. логику цветов уровней;
4. UI sans + reading serif;
5. допустимые radius/elevation/density traits и явно отвергнутые признаки.

Только после записи `Phase 1 — accepted` начинается Phase 2 Brand and tokens. Ответы о знаке, вердиктах и продуктовых потоках являются обязательными inputs, но сами по себе не принимают весь art direction.

## Открытые вопросы

- Какое art direction будет выбрано после сравнения трёх исполняемых вариантов?
- Логика цвета уровня различается по направлениям (A — одна чернильная лестница,
  B — три отдельных приборных оттенка, C — почти нейтральные тона плюс печатная буква
  н/п/х). Какая из трёх логик принимается?
- Финальная пара шрифтов фиксируется вместе с направлением; после выбора лишние
  `@fontsource*` пакеты удаляются.
- Какой clock-skew threshold применять к offline submission около deadline.
- Подтвердить UX для одинакового idempotency key с различающимися payload.
- После фиксации math corpus проверить subset/форматы KaTeX fonts и повторно измерить precache.
- Является ли «вернуть на доработку» отдельным action/state; `REJECTED_ANSWER` зарезервирован для отрицательного результата после перепроверки.
- Кто видит методическое событие просмотра подсказки и нужно ли хранить отказ конкретного teacher от проверки.
