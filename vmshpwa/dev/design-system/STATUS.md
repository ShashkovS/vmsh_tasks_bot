# Design-system status

Этот файл — журнал gates. Визуальная модель обновляет evidence и вопросы, но ставит `accepted` только после явного решения владельца продукта.

| Фаза                     | Статус             | Принято    | Evidence/решение                                                             |
| ------------------------ | ------------------ | ---------- | ---------------------------------------------------------------------------- |
| 1. Art direction         | accepted           | 2026-07-23 | Направление B принято как основа + заимствования из C. Журнал решений ниже.  |
| 2. Brand and tokens      | accepted           | 2026-07-23 | Токены + бренд приняты владельцем. Журнал решений ниже.                      |
| 3. UI primitives         | not started        | —          | Разблокирована; следующая фаза.                                              |
| 4. Product components    | blocked by phase 3 | —          | —                                                                            |
| 5. Pages and flows       | blocked by phase 4 | —          | Существующие prototype pages — content skeletons, не принятый visual design. |
| 6. Storybook and testing | blocked by phase 5 | —          | Текущая Storybook-конфигурация — инфраструктурный фундамент.                 |
| 7. Final acceptance      | blocked            | —          | —                                                                            |

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

```text
2026-07-23 — Phase 1 — accepted
Decision owner: Сергей Шашков (владелец продукта)
Chosen option and exact combination:
  Направление B «Мастерская» как основа — нейтральный рабочий холст, панели с
  умеренным radius и мягкой elevation, зебра в Staff-таблицах, брендовый знак B
  (скруглённый прямоугольник «179» с антенной) + его палитра и простой sans
  wordmark «ВМШ 179». Шрифты B (IBM Plex Sans UI + Source Serif 4 reading) —
  стартовая пара, license/subset/budget подтверждаются в Phase 2.
  Заимствования из C:
    - индикатор уровня — нейтральный буквенный chip (н/п/х + short_code), без
      насыщенной per-level заливки; «уровень, а не оценка», без давления;
    - номер задачи — без рамки/бордера вокруг него.
  Level-color logic: уровень несёт буква + short_code на нейтральном chip;
  per-level hue остаётся приглушённым служебным семейством для данных
  (charts/violin distribution), не как статусная заливка и не как verdict.
  Иконки продуктов и bottom-nav — Lucide; брендовый знак не используется как
  интерфейсная иконка.
Rejected traits:
  A — бумажная метафора листка и hairline-вместо-панели;
  C — почти прямые углы 2px и двойные линейки;
  насыщенные per-level цветные чипы уровня (эффект «ты пока слабый»).
Evidence stories: Exploration/Art direction (вариант B; A/C выброшены).
Known follow-ups:
  - финальная font pair и точные level-color токены фиксируются в Phase 2;
  - экранные уточнения (тип→иконка, «Зачтено» вместо «Верный ответ», полная
    шкала вердиктов, одна строка «Подсказка/Решение» скрытая до публикации,
    короткий уровень + сортировки в очереди учителя, быстрый поток проверки,
    провенанс human/AI) зафиксированы в docs/product-ux-decisions-2026-07.md.
```

```text
2026-07-23 — Phase 2 — accepted
Decision owner: Сергей Шашков (владелец продукта)
Chosen option and exact combination:
  Token system primitive→semantic→component; палитра B; цвета уровней
  категориальные (teal/violet/rose/ochre/neutral); ступени вердикта −…+;
  provenance human/AI; светлая и тёмная темы; шрифты IBM Plex Sans (UI) +
  Source Serif 4 (reading); знак «179» + wordmark + product icons + правила
  использования; density Student/Family/Staff.
Evidence stories: Foundations/Tokens, Foundations/Brand.
Checks: contrast 70×2 AA; Storybook 11/11; Vitest 7/7; pytest 11/11; build.
Known follow-ups:
  - visual baselines обновляются после первой реальной страницы (плейсхолдер
    «Сейчас» будет переписан) — сейчас 3 visual-теста ожидаемо расходятся ~3%;
  - сабсеттинг самих KaTeX-шрифтов (основной вес precache);
  - «несколько внутренних реакций учителя на одну проверку» — открытый вопрос.
```

## Фаза 1 — принято (evidence)

Направление B принято 2026-07-23; варианты A и C выброшены, `Exploration/*` удалён
после приёмки (решение и скриншоты зафиксированы в журнале решений выше). Ниже —
исходное описание evidence на момент сравнения A/B/C.

Stories (удалены после приёмки): `Exploration/Art direction` — «A · Листок»,
«B · Мастерская», «C · Архив», каждая в светлой и тёмной теме, плюс «Сравнение A / B / C».
Глобальные переключатели Storybook: тема, плотность (Школьник / Семья / Учитель), анимация.

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

## Phase 2 — принято (evidence)

Phase 2 принята владельцем 2026-07-23 (токены + бренд, журнал решений выше). Ниже — что вошло в фазу. Phase 1 принята тогда же (направление B + заимствования из C). Варианты A и C выброшены, `Exploration/*` удалён.

Phase 2 перевела B в слои `primitive → semantic → component` в `packages/ui/src/styles`.

**Сделано (token core, зелёный чекпоинт):**

- `globals.css` перестроен: primitive neutral OKLCH-шкала → semantic роли → component токены; светлая и тёмная темы;
- семейства: surfaces/text/borders/interactive/focus/selection/link/overlay; status success/warning/danger/info (base/-foreground/-surface/-border); **уровни — категориальные приглушённые hue (teal н / violet п / rose х / ochre 4-й / neutral fallback), не градиент, отдельно от status и verdict**; verdict scale negative→positive + none; provenance human / AI; unread; connection; chart 1–8 + grid/axis/reference; annotation pen/highlight/comment/selection;
- шрифты B self-hosted (`@fontsource/ibm-plex-sans` + `@fontsource-variable/source-serif-4`) как зависимости `@vmsh/ui`, кириллический subset, в precache;
- типографика (type scale + tabular numerals + math chain), radius/elevation/z-index/motion/density (Student/Family/Staff через `data-density`), container widths;
- **brand-assets**: repo-native SVG в `packages/ui/src/brand/marks.tsx` — `Sign179`, `Wordmark`, `IconStudent/Family/Staff`, всё `currentColor` (monochrome/print/обе темы); знак «179» читаем до 16 px; правила использования (clear space / min size / запрещённые трансформации / forced colors) в `Foundations/Brand`; `apps/*/public/icon.svg` (any) + production PNG `icon-192/512.png` (any) и `icon-maskable-512.png` (maskable, safe area); манифест: раздельные any/maskable + палитра B (`#205f7d` / `#edeff1`) — закрыт давний анти-паттерн одной `any maskable` SVG;
- `Foundations/Tokens` + `Foundations/Brand` stories; light/dark/Staff-density; матрица независимости уровень × статус × вердикт × автор;
- цветовые решения (палитра уровней teal/violet/rose, ступени вердикта) **подтверждены владельцем 2026-07-23**;
- контраст: `node dev/design-system/tokens-contrast-audit.mjs` — **70 пар × 2 темы проходят WCAG 2.2 AA**;
- гейты: format, lint (js + stylelint), typecheck, Storybook 11/11 (axe error), Vitest 7/7, pytest 11/11, build — зелёные;
- forced-colors: смысл не зависит от цвета (символ+подпись), фокус остаётся видимым системным цветом; `@media (forced-colors: active)` в globals.

**Полировка сделана (2026-07-23):** specimens spacing/motion + density Student↔Staff на одной форме в `Foundations/Tokens`; `Exploration/*` A/C удалён (B перенесён в реальные токены; знак — в `packages/ui/src/brand`); лишние `@fontsource` (inter/literata/golos-text/pt-serif) удалены; production PNG 192/512 any + maskable для manifest сгенерированы; precache подрезан globIgnores (убраны greek/vietnamese/latin-ext/cyrillic-ext слайсы: 2325→2031 KiB). Density теперь применяется на любом контейнере (`[data-density]`), не только на root.

**Правки принципов (owner feedback):** условие всегда перед глазами — подсказка/решение раскрываются дополнительно, не вкладками (поправлен Tabs-пример в primitives); школьник видит слово («Начинающие»), не голый код «н». Записано в `docs/product-ux-decisions-2026-07.md`.

**Остаётся фоном:** сабсеттинг самих KaTeX-шрифтов (сейчас основной вес precache).

Token core + brand + полировка готовы и зелёные (Storybook 11/11, contrast 70×2 AA, build).

**Следующее — Phase 3 UI primitives** (Base UI/shadcn на принятых токенах: density-варианты, focus/keyboard, states). Затем Phase 4 product components и только после — страницы, начиная со Student «Сейчас» в `mobile-light` (порядок — в `docs/product-ux-decisions-2026-07.md`). Visual baselines обновляются после первой реальной страницы.

## Открытые вопросы

- Какой clock-skew threshold применять к offline submission около deadline.
- Допускать ли несколько внутренних реакций учителя на одну проверку (сейчас — одна).
- Подтвердить UX для одинакового idempotency key с различающимися payload.
- После фиксации math corpus проверить subset/форматы KaTeX fonts и повторно измерить precache.
- Является ли «вернуть на доработку» отдельным action/state; `REJECTED_ANSWER` зарезервирован для отрицательного результата после перепроверки.
- Кто видит методическое событие просмотра подсказки и нужно ли хранить отказ конкретного teacher от проверки.
