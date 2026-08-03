# Design-system status

Этот файл — журнал gates. Визуальная модель обновляет evidence и вопросы, но ставит `accepted` только после явного решения владельца продукта.

| Фаза                       | Статус            | Принято    | Evidence/решение                                                                       |
| -------------------------- | ----------------- | ---------- | -------------------------------------------------------------------------------------- |
| 1. Art direction           | accepted          | 2026-07-23 | Направление B принято как основа + заимствования из C. Журнал решений ниже.            |
| 2. Brand and tokens        | accepted          | 2026-07-23 | Токены + бренд приняты владельцем. Журнал решений ниже.                                |
| 3. UI primitives           | accepted          | 2026-07-23 | Владелец направил к Phase 4 («всё нравится»). Набор примитивов готов.                  |
| 4. Product components      | accepted          | 2026-07-25 | Владелец: «в остальном вроде ок», направил к фазам 5–7; partial validation исправлена. |
| 4M. Multi-course extension | changes requested | —          | Добавлен ClassroomDeliveryPreview; component/story ещё нужно реализовать.              |
| 5. Pages and flows         | changes requested | —          | `/staff/classrooms` требует отдельный confirm→preview→send delivery step.              |
| 6. Storybook and testing   | changes requested | —          | Предыдущие 137 tests зелёные; новая delivery interaction matrix ещё не реализована.    |
| 7. Final acceptance        | ready for review  | —          | Functional gates зелёные; multi-course Student visual diff ждёт решения владельца.     |

Допустимые статусы: `not started`, `in progress`, `ready for review`, `changes requested`, `accepted`, `blocked by phase N`.

```text
2026-07-26 — Phase 4M — ready for review
Decision owner: ожидается Сергей Шашков
Implemented:
  CourseCard/CourseContext/CourseGroupSwitcher; course/group Staff catalog,
  independent schedule and Telegram inheritance; synonym merge/split, merged
  chronology and combined review; multi-course in-person event; course-scoped
  progress; corresponding Student/Family/Staff page compositions.
Evidence stories:
  Product/Courses--student-multiple-courses;
  Product/Courses--active-and-allowed-groups;
  Product/Staff-admin--course-and-group-catalog;
  Product/Staff-admin--independent-schedules;
  Product/Staff-admin--telegram-bindings;
  Product/Staff-data--synonym-merge-and-split;
  Product/Feedback--synonym-merged-timeline;
  Product/Review--synonym-combined-case;
  Product/Classrooms--multi-course-inherited-event;
  Product/Progress--courses-separated;
  Pages/Student, Pages/Family and Pages/Staff multi-course stories from the
  development-plan design map.
Checks:
  make pwa-lint, pwa-typecheck, pwa-test, pwa-storybook-test и pwa-build — green;
  ESLint + Stylelint и strict TypeScript — green; Vitest 29/29; Python PWA 11/11;
  Storybook browser mode 31 file / 137 tests с addon-a11y error — green;
  production Storybook build и production builds Student/Family/Staff — green;
  Student/Family injectManifest: 103/102 precache entries;
  Markdown local links: 48 files — green; git diff --check — green.
Manual visual review:
  На agent Storybook :6106 просмотрены mobile-light Student/Family и desktop
  course catalog, independent schedules, Telegram bindings, synonym timeline,
  combined review, course progress и multi-course classroom event/page.
  Исправлены глобальный attendance control, который противоречил per-course
  mode, provenance combined review, русские подписи и interaction fixture.
Production visual regression:
  Staff weekly dashboard совпадает с baseline в Chromium/WebKit/Firefox;
  Student current week ожидаемо отличается во всех трёх браузерах: высота
  1188→1615 px и около 4% пикселей из-за новых course cards. Snapshots не
  обновлены и ждут визуального решения владельца.
Known follow-ups:
  Backend endpoints and migrations are explicitly not implemented. Owner must
  принять новые Storybook-сценарии и Student visual diff до обновления baseline.
  Решение 27 июля добавило узкий ClassroomDeliveryPreview: explicit PWA/Telegram
  send только Student, без Family delivery и auto-resend. Его component/page
  story и interaction tests ещё не реализованы и честно возвращают Phase 4M–6
  в changes requested.
```

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
2026-07-27 — Phase 4M/5/6 — changes requested
Decision owner: Сергей Шашков (владелец продукта)
Chosen option and exact combination:
  Confirm classroom plan обновляет Student/Family state без notification.
  Затем admin отдельно открывает preview, выбирает PWA и/или Telegram и
  отправляет personal classroom message только Student. Telegram означает
  личный bot dialogue, не channel. Изменение плана не вызывает auto-resend.
Rejected traits:
  notification на каждый confirm/change; Family classroom push/Telegram;
  использование общего broadcast composer; показ token/chat ID; draft send.
Evidence stories required:
  Product/Classrooms--delivery-preview;
  Product/Classrooms--delivery-changed-after-send;
  Pages/Staff--classroom-delivery;
  interaction: confirm is silent, explicit channels/send, stale preview,
  partial failure/retry, no Family recipient, no automatic resend.
Known follow-ups:
  Компонент и stories ещё не реализованы; snapshots до owner review не менять.
```

```text
2026-07-25 — Phase 4 — accepted
Decision owner: Сергей Шашков (владелец продукта)
Chosen option and exact combination:
  Владелец принял компонентный корпус формулировкой «в остальном вроде ок» и
  явно поручил продолжить фазы 5–7. Последняя правка gate: TestAnswer не
  показывает format error во время partial input; ошибка появляется после
  ухода из целого control или submit. Weekday — семь кнопок пн–вс.
Evidence stories:
  Product/Test answer — Gallery, Tuple, Partial compound format, Weekday;
  остальные Product/* stories из инкрементов Phase 4.
Checks:
  lint/typecheck; Vitest 21/21; PWA pytest 11/11; Storybook browser tests 85/85
  с addon-a11y error. Gallery вручную проверена в agent Storybook на 6106.
Known follow-ups:
  Classroom dense/local-draft matrices и финальные cross-theme/viewports входят
  в Phase 6; это coverage follow-up, а не блокер принятого визуального языка.
```

```text
2026-07-25 — Phase 5 — ready for review
Decision owner: ожидается Сергей Шашков
Implemented:
  Реальные compositions для Student, Family и Staff; отдельные login shells;
  общий responsive AppShell/PageLayout; основные ready и non-happy states;
  Student test/written/oral/result/news/progress/profile; Family read-only child
  context без self-check; Staff dashboard/review/content/classrooms/forbidden.
Exact evidence:
  apps/{student,family,staff}/src/pages.tsx и pages.stories.tsx;
  packages/app-shell/src/{app-shell,page-layout}.tsx;
  apps/staff/src/routes/classrooms.tsx.
Known follow-ups:
  fixtures/callbacks заменяются настоящими query/API по development-plan phases;
  владелец визуально принимает mobile-light first flow до статуса accepted.
```

```text
2026-07-26 — Phase 6 — ready for review
Decision owner: ожидается Сергей Шашков
Implemented:
  Pages/Student, Pages/Family, Pages/Staff; loading/empty/error/offline matrices;
  classroom 15-room/200-student и local-draft reload/clear stories;
  login reveal, Family read-only, test validation, Staff verdict/classroom tests;
  компактная внутренняя teacher reaction с полным текстом и сочетаниями
  Mod+Alt+1–4, которые работают при фокусе в комментарии и не ловят AltGraph;
  bounded publication scheduler: 12rem datetime-local и actions на новой строке.
Checks:
  Storybook browser mode 24 files / 121 stories, addon-a11y test:error — green.
  Вручную просмотрены Student Today, Staff review workspace и Staff classrooms
  на agent Storybook :6106. Найден и исправлен horizontal Tabs selector.
  `Product/Review--Feedback guard` и `Feedback reaction shortcuts` проверены
  в desktop viewport; shortcut переключает reaction 1→4 из textarea.
  `Product/Staff admin--Publication scheduling` проверена при 900px и 600px:
  input 192px, соседняя колонка начинается после его правой границы.
Known follow-ups:
  owner visual approval относится к Phase 7; fixtures/callbacks остаются
  прототипами до вертикальных срезов development plan.
```

```text
2026-07-25 — Phase 7 — ready for review
Decision owner: ожидается Сергей Шашков
Automated proof:
  format, ESLint, strict TypeScript и production Vite/PWA build — green;
  Vitest 21/21; Python PWA tests 11/11;
  Storybook browser mode 24 files / 121 stories, addon-a11y test:error — green;
  Playwright production preview 36/36 в Chromium, WebKit и Firefox, включая
  shell/base path, audience isolation, theme, WebSocket resync, PWA update и
  Student/Staff visual baselines.
Visual proof:
  ожидаемые Phase-5 page changes просмотрены до update; baseline хранится в
  e2e/__screenshots__ и успешно прошёл повторный запуск без update-флага.
Remaining owner gate:
  принять mobile-light страницы Phase 5, Storybook corpus Phase 6 и итоговую
  ручную проверку ключевого Student/Staff flow из 07-acceptance-checklist.md.
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
  - внутреннюю реакцию учителя уточнили 24 июля: ровно одна на проверку, изменение/удаление в течение часа.
```

```text
2026-07-23 — Phase 3 — accepted
Decision owner: Сергей Шашков — «пока всё нравится», направил к Phase 4.
Chosen option and exact combination:
  Обязательный набор примитивов на Base UI/shadcn + принятые токены; density
  token-driven (touch школьник / compact staff, не size-prop); overlays с
  focus/keyboard/восстановлением фокуса; новые Alert + Progress; interaction-
  тесты (форма/диалог/меню/тост/accordion/table/radio) + addon-a11y error.
Evidence stories: UI/Controls, UI/Overlays, UI/Selection, UI/Structure, Foundations/*.
Checks: Storybook 26/26; contrast 72×2 AA; lint/typecheck/build.
Known follow-ups: —
```

```text
2026-07-24 — Phase 4 — changes requested
Decision owner: Сергей Шашков (владелец продукта)
Chosen option and exact combination:
  Аудитории разделяются на глобальный каталог, наследуемую версию схемы
  «аудитория → группа» и версионируемый план школьников для занятия.
  `/staff/classrooms` получает три вкладки: «Каталог», «По группам»,
  «Школьники». У комнат нет capacity/weights и drag interaction; используются
  select/move, preview, recalculate и confirm. Student и Family видят
  assigned/reassigning/not-applicable; исторически предполагался автоматический
  Student push. Решение 27 июля выше заменяет его explicit admin delivery batch.
Rejected traits:
  Старый единый ClassroomPlanner с capacity, per-lesson room records и простой
  перестройкой без inherited/materialized/stale version states.
Evidence stories:
  Требуются новые Product/Staff admin classroom catalog/layout/plan stories и
  Student/Family assignment-state stories; существующая story не является proof.
Known follow-ups:
  После реализации повторно пройти interaction/a11y/visual gate Phase 4 и только
  затем вернуть фазу в ready for review. Остальные зелёные инкременты не отклонены.
```

```text
2026-07-24 — Phase 4 — ready for review
Decision owner: ожидается решение Сергея Шашкова (владельца продукта)
Chosen option and exact combination:
  Замена старого ClassroomPlanner завершена. Реализованы отдельные компоненты
  ClassroomCatalog, ClassroomGroupLayout, ClassroomStudentPlanner и
  ClassroomAssignmentStatus. Они покрывают каталог active/hidden/duplicate,
  inherited/materialized/conflict layout, preview/stale/reassigning/empty/no-room
  assignment plan, фактические 6/5/2 аудитории, подтверждение и публичные
  Student/Family states. DnD и capacity отсутствуют.
Evidence stories:
  Product/Classrooms — 12 stories: catalog active/hidden/duplicate; inherited
  6/5/2, materialized confirm, optimistic conflict; plan preview/confirm, stale,
  reassigning/no-room, empty group; Student/Family state matrix; mobile Staff.
Checks:
  Prettier, ESLint и package typecheck — green; Vitest 7/7; Storybook browser
  tests 83/83 с addon-a11y error; production Storybook build — green. В браузере проверены
  desktop light layout, desktop dark blocking incident, mobile Staff, duplicate
  handling и Student/Family states; console errors отсутствуют.
Known follow-ups:
  Только визуальное решение владельца по gate Phase 4. Page-level интеграция
  `/staff/classrooms` относится к Phase 5; snapshots не обновлялись.
```

```text
2026-07-25 — Phase 4 — changes requested
Decision owner: Сергей Шашков (владелец продукта)
Chosen option and exact combination:
  Classroom assignments используют только компактные select, включая bulk mode;
  комнаты складываются flex-wrap и выдерживают 6–15 комнат/~200 школьников.
  Нужны group marker/tint и «очно/распределено», отдельные неназначенные,
  возраст на сегодня, класс, auto-strength 0–10, room averages возраста/класса/силы, fuzzy search+jump,
  classroom history и confirmation при выборе комнаты другой группы.
  Все значимые Student/Staff drafts переживают reload: serializable state в
  localStorage, blobs/outbox в Dexie, очистка только после receipt/confirm/discard.
  Статистика никогда не отмечает школьника на распределении и не сравнивает с группой.
Rejected traits:
  DnD для 15 комнат; большие student cards; autosave каждого select на server;
  self marker/«выше среднего» в violin.
Evidence stories:
  Существующие Product/Classrooms остаются baseline, но не закрывают новый gate.
  Требуются density, missing data, fuzzy/history, bulk/cross-group и draft stories.
Known follow-ups:
  После реализации повторить Storybook interaction/a11y/visual checks. Phase 4
  возвращается в ready for review только после закрытия всех перечисленных states.
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
- Staff сохраняет базовые label/alt/ARIA/contrast и axe gate; полноценный keyboard-аналог специализированного DnD не обязателен;
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

## Phase 3 — UI primitives (в работе)

**Инкремент 1 — actions/inputs + density-механизм (зелёный):**

- density стала **token-driven**: `Button`/`Input`/`Textarea`/`Select` берут высоту из `--touch-target` / `--touch-target-primary` — один и тот же компонент touch-размера у школьника (44/48px) и compact у учителя (32px) через `data-density`, без size-prop; `bg-surface`, `placeholder` затемнён до AA;
- `Badge` получил семантические тона (success/warning/danger/info/neutral) — surface-чипы для статусов; level/verdict строятся поверх в Phase 4;
- `UI/Controls` stories: Density (школьник↔учитель рядом), States, Badge tones, **FormValidation** с interaction-тестом (ошибка только после submit, `aria-describedby` связь, значение сохраняется, успех);
- гейты: format, lint (js+css), typecheck, **Storybook 15/15** (axe error), **contrast 72×2 AA** (добавлен placeholder), build — зелёные.

**Инкремент 2 — overlays + selection (зелёный):**

- `UI/Overlays`: Dialog (destructive confirm, focus в диалоге, Escape закрывает и **возвращает фокус** на триггер), DropdownMenu (открытие + клавиатурный выбор), Toast (тост с действием), Popover, Tooltip — с 3 interaction-тестами;
- `UI/Selection`: `Checkbox` (checked/indeterminate/unchecked/disabled), `Switch`, **новый `RadioGroup`** (SELECT_ONE тестовый ответ) — interaction-тест выбора + density;
- поймано и обойдено: `MenuLabel` требует обёртки `MenuGroup`; контент оверлея кратко «не виден» во время open-анимации (retry-ассерты `findBy*`); Base UI дублирует заголовок тоста в aria-live (`findAllByText`);
- гейты: Storybook **22/22** (axe error), lint (js+css), typecheck, build — зелёные.

**Инкремент 3 — structure/data + Alert/Progress (зелёный):**

- `UI/Structure`: `Accordion` осознанное раскрытие подсказки/решения (панель закрыта до действия — interaction-тест на `aria-expanded`); `Table` очереди проверки — caption, сортируемый заголовок с `aria-sort` (interaction-тест переключения), выбранная строка, empty и loading (skeleton), **Staff-density компактнее через `in-data-[density=staff]`**; `Skeleton`;
- новые примитивы: **`Alert`** (баннеры связи offline/syncing/success, тон на иконке/границе, текст читаемый `foreground`), **`Progress`** (сжатие/загрузка фото);
- гейты: Storybook **26/26** (axe error), lint (js+css), typecheck, build — зелёные.

**Phase 3 завершена (ready for review).** Обязательный набор примитивов покрыт на Base UI/shadcn + принятые токены: actions/inputs (Button/Input/Textarea/Field/Label/Checkbox/Switch/Select/RadioGroup), overlays (Dialog/Drawer/Popover/Tooltip/DropdownMenu/Toast), structure/data (Tabs/Accordion/Badge/Card/Table/Separator/Skeleton), плюс Alert/Progress. Density token-driven, focus/keyboard/states/interaction-тесты, contrast 72×2 AA. Ждёт приёмки владельцем перед Phase 4 product components.

Затем Phase 4 product components и только после — страницы, начиная со Student «Сейчас» в `mobile-light`. Visual baselines обновляются после первой реальной страницы.

## Phase 4 — product components (в работе)

Продуктовые компоненты живут в новом пакете **`@vmsh/product`** (домен-зависимые; `@vmsh/ui` остаётся нейтральным). Пакет зависит от `@vmsh/ui`, Tailwind `@source` добавлен. Компоненты принимают view-model + callbacks, не делают fetch; view-model типы — в пакете, runtime Zod-контракты придут с API.

**Инкремент 1 — ядро task/verdict (зелёный):**

- `LevelChip` — слово + буквенный маркер (школьник видит слово, не код); `compact` = только буква с именем в accessible name (`role="img"`) для плотной Staff-очереди;
- `VerdictMark` + `verdict-registry` — шкала из настроек курса (`buildVerdictRegistry`, пресеты binary/ternary/full из `helpers/consts.py`); символ первичен, подпись — accessible name; **оценка ИИ визуально отделена** (dashed + 🤖 + «оценка ИИ»);
- `TaskTypeIcon` — 4 типа → 3 для школьника (гибрид=oral), accessible name + правило сдачи (`taskTypeRule`);
- `DeadlineNotice` — абсолютное+относительное время, `<time>`, состояния open/closing-soon/closed;
- `TaskListItem` — номер+иконка+вердикт-или-статус+«новое»+название, вся строка — кнопка; ровно как одобрено на скриншотах (тип→иконка, номер без рамки, «Зачтено»/градуированная шкала);
- `Product/Task` stories на фикстурах листка 21н + interaction-тест открытия задачи;
- гейты: Storybook **30/30** (axe error), lint (js+css), typecheck, build — зелёные.

**Инкремент 2 — чтение задачи (зелёный):**

- `@vmsh/content`: `MathHtml` рендерит санитайзенный HTML + client-side KaTeX (`renderMathInElement`, `output: htmlAndMathml`, `trust: false`), формула не обрезается (`.katex-display` — локальный scroll), выделение формул отключено. Добавлено: широкие таблицы автоматически оборачиваются в `.vmsh-scroll-x` (локальный горизонтальный scroll, не страница), theorem-like callout (`.vmsh-note`), нумерованная формула с deep-link (`.vmsh-eq`/`.vmsh-eqno`, `:target` подсветка). Story `Product/Mathematical document` показывает вводный текст, подпункты, callout, inline+display math, широкую таблицу с числовыми `td`-формулами (заголовки — обычный текст ради screen reader) и code-like ответ; interaction-тест проверяет рендер KaTeX и обёртку таблицы;
- `@vmsh/product` `ProblemHeader` — фиксированная рамка задачи: номер, тип **иконкой** (accessible name + hover title, не слово), `LevelChip` словом, финальный `VerdictMark` с подписью, ссылка «История»; условие рендерит страница ниже — заголовок его не прячет;
- `ConsciousDisclosure` + пресеты `HintDisclosure`/`SolutionDisclosure` — «условие всегда перед глазами»: раскрытие идёт **ниже** условия и аддитивно; первое открытие требует осознанного подтверждения (решение «нельзя развидеть»), затем переключается свободно; недоступное (до дедлайна) состояние — locked, а не мёртвая кнопка;
- `ZoomableFigure` — рисунок (TikZ/SVG) с zoom in/out/reset кнопками (keyboard-operable), локальный scroll увеличенного, `role="img"` + alt как текстовая альтернатива, отдельная подпись;
- `Product/Reading` stories (заголовок, рисунок, disclosure, «чтение задачи целиком») на фикстуре 21н «Расстановка ладей» + interaction-тесты: условие видно до любых раскрытий, подтверждение появляется раньше текста, заблокированное решение не раскрывается, zoom меняет масштаб;
- гейты: Storybook **34/34** (axe error), lint (js+css), typecheck, build — зелёные.

**Инкремент 3 — ввод тестовых ответов (переработан 25 июля, требует повторного gate):**

- `answer-spec.ts` описывает все 23 текущих `ANS_TYPE`; `answer-validation.ts` зеркалит `strip()+fullmatch` из `helpers/checkers.py`, включая per-problem `ans_validation`, но оставляет server авторитетом;
- `TestAnswer` показывает заметную format error, не выводит «Отправится» для tuple, показывает «Распознано» для list только после legacy-compatible parsing и передаёт видимый русский label `SELECT_ONE`;
- `Product/Test answer` содержит scalar invalid, tuple invalid, list parsing, exact-label choice и галерею всех 23 типов; добавлены unit fixtures legacy boundaries;
- гейты: Storybook **39/39** (axe error), lint (js+css), typecheck, build — зелёные.

**Инкремент 4 — письменная сдача (переработан 25 июля, требует повторного gate):** `AttachmentView` + `AttachmentItem`/`AttachmentList` показывают реальные thumbnails во всех processing/upload/error states, переупорядочивание вверх/вниз, поворот, удаление и retry. `SubmissionComposer` сохраняет text/photo/offline states. Отдельные `SubmissionReceipt`, reference number и story-квитанция удалены: успешная сдача должна становиться обычной записью треда.

**Инкремент 5 — результат, тред, аннотации (зелёный):** `VerdictPanel` (вердикт + комментарий; human/AI по-разному, ИИ не спутать с преподавателем); `AttemptTimeline` (последний вердикт сразу, история раскрывается, без «номера попытки» и обвинительного тона); `FeedbackThread`/`ThreadMessage`/`FeedbackAttention` (автор/время/канал; асимметричная видимость как permission state; индикатор непрочитанного); `reaction`-registry + `ReactionPicker`/`ReactionChip` (легаси-реакции 0/100/200/300 с видимостью: ученик скрыт от учителя/виден admin, внутренняя учителя скрыта от ученика); `AnnotationOverlay` (перо/выделение/нумерованные комментарии над неизменяемой работой). `Product/Feedback` stories + interaction-тесты (выбор реакции, раскрытие истории, комментарий-аннотация).

**Инкремент 6 — Telegram-rich новости (переработан 25 июля, требует повторного gate):** structured model дополнен headings, mark/sub/sup, lists, code, details, tables и divider. Основная `Product/News--post` показывает полное условие текстом с math/list/details без screenshot; corpus привязан к `_external_pipelines/ChatExport_2026-07-25`. Card/detail, PWA/Telegram previews и editorial states сохранены.

**Инкремент 7 — connectivity (зелёный):** `ConnectionBanner` (online ненавязчив; offline/reconnecting объясняют влияние на действие; conflict — не исчезающий toast, требует решения); `SyncIndicator` (счётчик очереди → outbox, тихо когда нечего слать); `UpdatePrompt` (не рушит черновик); `PushPermissionCard` (объясняет категории до системного запроса, уважает отказ). `Product/Connectivity` stories + interaction-тесты.

**Инкремент 8 — рабочее место Staff (переработан 26 июля, требует повторного gate):** queue сохранена, а detail теперь одна колонка `evidence → thread → teacher reply/verdict`; teacher verdict/reaction controls компактны, но сохраняют точный текст. `MetadataGrid` получил dropdown-ячейки task type/answer type с TSV paste. `PublicationControl` независимо публикует/планирует/откатывает condition/hint/solution; открытый datetime editor ограничен 12rem, а действия вынесены на следующую строку без overlap соседних колонок. Полный `BroadcastComposer` убран из первой фазы story и обозначен как phase-two Markdown workflow. Остальные lock/data/upload/SOS surfaces сохранены.

**Инкремент 9 — прогресс (зелёный, требования уточнены):** зависимость `@visx/scale` (из каталога); `DistributionViolin` показывает только распределение группы и медиану — без маркера школьника и без словесного сравнения его с группой. `TrendWithBand` (линия + доверительная полоса) и график личной динамики shape-first, не только по цвету, с табличным эквивалентом в `<details>`; `StudentProgress` — словами («3 задачи зачтено»), спокойный streak относительно своей истории, без leaderboard/percentile/красных провалов. `Product/Progress` stories + interaction-тесты.

**Инкремент 10 — аудитории (доработан 25 июля, требует повторного gate):** layout теперь имеет group marker/tint и `очно/распределено`; planner использует flex-wrap room cards, отдельную секцию неназначенных, компактные строки с возрастом/классом/силой, room averages, fuzzy search+jump, checkbox bulk move, history action и callback подтверждения cross-group move. `mobile-staff-layout` содержит все student/room metrics. До принятия ещё нужны реальная local-draft story и отдельный dense fixture около 200 школьников; capacity/DnD отсутствуют.

**Исторический gate Phase 4:** результаты 83/83 относились к корпусу до финальных classroom/draft требований. Недостающие local-draft, 15-room/200-student и bounded publication-scheduler stories добавлены в Phase 6; актуальный browser gate — **121/121** с addon-a11y в режиме error. Phase 4 принят владельцем, дальнейшие решения фиксируются как Phase 5/6 review, а не возвращают принятую фазу в `changes requested`.

## Решения итогового продуктового опросника — 24 июля 2026

- Первый рабочий корпус: занятия 39–41 сезона 2025–2026, все три уровня; сначала полный online flow. Print, быстрый очный ввод, общий Staff→Telegram channel publisher и AI-интеграция — следующая версия; персональная classroom delivery Student входит в v1.
- Clock skew больше часа помечается для диагностики. Одинаковый idempotency key с другим payload не перезаписывает операцию и требует нового ключа после явного действия.
- На один verdict разрешена одна внутренняя teacher reaction и одна student reaction; обе меняются/удаляются в течение часа.
- Отдельного dispute/«вернуть на доработку» workflow в v1 нет: состояние интерфейса выводится из актуального registry verdict. `REJECTED_ANSWER` остаётся отрицательным результатом после перепроверки.
- Hint reveal хранится как служебное методическое событие и в v1 не показывается отдельной строкой ролям.
- Причина abandon не хранится; unsent teacher comment/annotation draft сохраняется локально.
- Значимая незавершённая работа Student/Staff сохраняется локально до server receipt/confirm или explicit discard: serializable drafts в `localStorage`, blobs/outbox в Dexie. Classroom edits не autosave-ятся на сервер по одному.
- Staff сохраняет базовые a11y label/alt/ARIA/contrast/axe; отдельный keyboard-аналог специализированного DnD не обязателен. Текущий classroom flow использует select, не DnD.
- Family self-check удалён из требований. Family видит полный student-visible thread/evidence, меняет level/mode и получает недельный итог без сравнения с группой.
- Полный набор решений и границ находится в `../development-plan/01-decisions-and-boundaries.md`; компонентные и page-требования синхронизированы в `04-product-components.md`, `05-pages-and-flows.md` и `07-acceptance-checklist.md`.

## Оставшийся инженерный follow-up

- После фиксации math corpus проверить subset/форматы KaTeX fonts и повторно измерить precache.

## Phase 4 reopened checkpoint: Student account batch creation — 2 August 2026

- Added `Pages/Staff--student-account-batch-creation` for the compact admin-only
  daily batch flow, canonical-login selection and reload-safe non-secret draft.
- Staff browser-mode run: 23/23 page stories passed with the a11y gate enabled.
- Initial historical bulk import remains a separate Phase 10 workflow; this
  story deliberately reuses the accepted single-account interaction.

## Phase 4 reopened checkpoint: searchable Staff audit — 2 August 2026

- Added the real dense Staff page stories `Pages/Staff/Audit--SearchableTimeline`
  and `Pages/Staff/Audit--EmptySearch`: object/search filters, actor, request ID and
  expandable before/after values.
- Browser interaction/a11y gate: **48 files, 231 tests passed**. The production
  route and API are also covered in Chromium, WebKit and Firefox.
- No visual baseline was updated. Owner review of desktop and compact/mobile table
  behaviour remains open; current implementation uses horizontal table scrolling on
  narrow screens rather than hiding audit fields.
- The accepted timeline fixture now also renders a real course update and exposes
  `course`/`group` filters; focused interaction/a11y remains **2/2 PASS**.
- The same timeline now includes a verified Telegram course destination and the
  `telegram_binding` filter with Russian field/action labels. Focused browser/a11y
  remains **2/2 PASS**; no visual baseline was updated.
- The timeline fixture now also shows a synonym split with provenance summary and
  exposes the `problem_synonym` filter. Focused interaction/a11y remains **2/2
  PASS**; no visual baseline was updated.
- The same dense fixture now shows a teacher-scope replacement and exposes the
  `staff_scope` filter with compact course/group summaries. Focused
  interaction/a11y remains **2/2 PASS**; no visual baseline was updated.

## Checkpoint 2 августа 2026 — Staff statistics page

- Добавлены stories `Pages/Staff/Statistics--HistoricalCourse` и
  `Pages/Staff/Statistics--NoCompletedRun` для реальной course/group-scoped
  страницы `/staff/statistics`.
- Визуальный контракт: плотная история занятий, компактная сводка и только
  анонимный Staff violin; никакого маркера отдельного школьника или выдачи
  student rows.
- Interaction/a11y full gate: `49 files / 233 passed`. Desktop и mobile-light
  390 px просмотрены вручную; таблица имеет собственную горизонтальную
  прокрутку. Visual snapshots сознательно не обновлялись до owner review.

## Checkpoint 2 августа 2026 — Staff operational dashboard

- Production `/staff/` использует новый `StaffDashboardView`, а не исторический
  prototype `Pages/Staff--weekly-dashboard`.
- Stories: `Pages/Staff/Dashboard--CurrentWeek`, `--TeacherScoped`,
  `--NoCurrentLessons`; данные соответствуют строгому runtime-контракту.
- Full interaction/a11y gate: `50 files / 236 passed`. Desktop и mobile-light
  390 px просмотрены вручную; snapshots не обновлялись до owner review.
- Общий технический gate этого среза: frontend unit `110 files / 586 passed`,
  lint/typecheck/production build — pass.

## Checkpoint 2 августа 2026 — письменная сдача: 1/2/10 страниц

- Storybook IDs: `Product/Submission--one-page`, `--two-pages`, `--ten-pages`.
- Interaction/a11y gate: **50 files / 239 PASS**; в двухстраничном состоянии
  проверяется перестановка, в десятистраничном — точная верхняя граница.
- Mobile-light 390 px и desktop 1280 px просмотрены в agent Storybook: без
  горизонтального overflow, все страницы и controls доступны.
- Snapshots не обновлялись. Финальное визуальное принятие владельцем остаётся
  открытым.

## Development Phase 6 — automated review-surface gate · 3 августа 2026

- Проверяемая Storybook-матрица включает queue/workspace, восстановленный
  draft, быстрые verdict/reaction shortcuts, annotation editor/read-only view,
  reviewed Student/Family states, admin reaction inbox, synonym combined case
  и private support dialogue.
- Актуальный browser interaction/a11y gate: **50 файлов / 239 PASS**;
  `addon-a11y` остаётся в режиме error.
- Production multi-context E2E: **3/3 PASS** в Chromium, WebKit и Firefox,
  включая скрытие Staff-only reaction и admin correction.
- Точный список story IDs и функциональных proof:
  [`phase6-consolidated-gates-2026-08-03.md`](../../../pwa_tests/reports/phase6-consolidated-gates-2026-08-03.md).
- Это автоматический gate, не визуальное принятие. Snapshots не обновлялись;
  owner review для review/correction/support surfaces остаётся открытым.

## Development Phase 10 — Staff metadata draft states · 3 августа 2026

- В production `ProblemReviewWorkflow` подключён принятый DraftPersistence
  contract для metadata grid: reload, runtime/account/revision isolation,
  optimistic conflict, explicit discard и receipt cleanup.
- Story IDs:
  `Pages/Staff/Content publication--metadata-draft-survives-reload`,
  `--metadata-draft-is-account-scoped`,
  `--metadata-conflict-keeps-draft`,
  `--match-then-review-metadata`.
- Focused interaction/a11y: **14/14 PASS**; полный Storybook browser gate:
  **241/241 PASS**. Production content flow: **3/3 PASS** в
  Chromium/WebKit/Firefox без retry.
- Proof и concrete implementation links:
  [`phase10-metadata-grid-drafts-2026-08-03.md`](../../../pwa_tests/reports/phase10-metadata-grid-drafts-2026-08-03.md).
- Это functional checkpoint, не новое визуальное принятие. Snapshots не
  обновлялись; owner visual review остаётся открытым.

## Development Phase 9 — Family course achievements · 3 августа 2026

- Production `FamilyCourseAchievements` показывает только известные спокойные
  личные достижения конкретного курса и использует те же подписи, что Student.
- Story `Pages/Family--course-achievements` проверяет две известные подписи,
  скрытие неизвестного server rule и отсутствие ranking/place/percentile.
- Focused interaction/a11y: **12/12 PASS**; полный browser gate:
  **242/242 PASS**. Lint, strict TypeScript и production builds — PASS.
- Это functional/design traceability checkpoint. Ручное visual acceptance не
  выполнялось, snapshots не обновлялись; streak/completed-lesson states будут
  добавлены вместе с соответствующими продуктовым правилами.

## Development Phase 8 — scheduled local-news editing · 3 августа 2026

- `Product/News moderation--Scheduled local` показывает edit action только для
  будущей local publication; Telegram-строки его не имеют, а опубликованная
  local news покрыта отдельным последующим checkpoint.
- `Pages/Staff/Local news composer--Editing scheduled` фиксирует неизменяемого
  получателя, редактируемые текст/время и отдельную подпись сохранения.
- Interaction/a11y входят в полный Storybook gate **245/245 PASS**; production
  news E2E **9/9 PASS** в Chromium, Firefox и WebKit проверяет reload-safe draft.
- Это функциональный checkpoint. Snapshots не обновлялись; ручное visual
  acceptance владельцем остаётся открытым.

## Development Phase 8 — Family notification settings · 3 августа 2026

- `Pages/Family/Notifications--Ready|Loading|Error|Push denied` фиксируют
  production states, пять допустимых Family-категорий и отсутствие ложных
  per-review/classroom controls.
- `Product/Connectivity--Push · состояния устройства` документирует loading,
  available, enabled, denied, unsupported и error для общего Student/Family
  `PushDeviceControls`.
- Focused interaction/a11y **22/22 PASS**, полный Storybook gate **250/250
  PASS**, production E2E **12/12 PASS** в трёх браузерах без retry.
- Snapshots не обновлялись; ручное visual acceptance владельцем остаётся
  открытым.

## Development Phase 8 — published local-news correction · 3 августа 2026

- `Product/News moderation--Published local correction` показывает revision,
  отметку «обновлено» и явное действие исправления только для local source.
- `Pages/Staff/Local news composer--Editing published` фиксирует неизменяемые
  owner/время и редактируемый plain text. Повторное уведомление явно исключено
  в тексте диалога.
- Focused Storybook browser-mode не стартовал из-за внешнего macOS Chromium
  `MachPortRendezvous` code 141; interaction/a11y не объявлены пройденными.
- Unit **594 PASS**, lint, strict TypeScript и production build — PASS.
  Snapshots не обновлялись; owner visual acceptance остаётся открытым.
