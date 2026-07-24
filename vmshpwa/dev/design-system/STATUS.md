# Design-system status

Этот файл — журнал gates. Визуальная модель обновляет evidence и вопросы, но ставит `accepted` только после явного решения владельца продукта.

| Фаза                     | Статус             | Принято    | Evidence/решение                                                                 |
| ------------------------ | ------------------ | ---------- | -------------------------------------------------------------------------------- |
| 1. Art direction         | accepted           | 2026-07-23 | Направление B принято как основа + заимствования из C. Журнал решений ниже.      |
| 2. Brand and tokens      | accepted           | 2026-07-23 | Токены + бренд приняты владельцем. Журнал решений ниже.                          |
| 3. UI primitives         | accepted           | 2026-07-23 | Владелец направил к Phase 4 («всё нравится»). Набор примитивов готов.            |
| 4. Product components    | ready for review   | —          | Инкременты 1–9 готовы (`@vmsh/product`), гейты зелёные. Ждёт приёмки владельцем. |
| 5. Pages and flows       | blocked by phase 4 | —          | Существующие prototype pages — content skeletons, не принятый visual design.     |
| 6. Storybook and testing | blocked by phase 5 | —          | Текущая Storybook-конфигурация — инфраструктурный фундамент.                     |
| 7. Final acceptance      | blocked            | —          | —                                                                                |

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

**Инкремент 3 — ввод тестовых ответов (зелёный):**

- `answer-spec.ts` — view-model `AnswerSpec` поверх всех ~24 `ANS_TYPE` (helpers/consts.py): тип сворачивается к одному из четырёх архетипов (`answerInputKind`: scalar / tuple / list / choice), плюс `answerInputMode` (numeric/decimal/text — правильная экранная клавиатура) и `defaultAnswerHint` — понятная русская подсказка + пример на каждый тип;
- `TestAnswer` — один компонент на все типы: скаляр (Input с нужным inputMode), кортеж фиксированной длины (int-2/3/4 — отдельные поля, у каждого accessible name), список через запятую (int-seq/int-set/frac-seq/multiset — Input + живой предпросмотр разобранных элементов; семантика порядка/повторов — в подсказке), выбор одного варианта (RadioGroup). Компонент неконтролируемый внутри, отдаёт нормализованную строку ответа через `onChange` — правильность решает сервер. **Формат всегда объяснён словами + пример** (школьник видит внятный текст, не код);
- `Product/Test answer` stories (скаляр/кортеж/список/выбор + галерея типов) + interaction-тесты: ввод скаляра, сборка кортежа «1, 7, 9», предпросмотр списка, выбор варианта;
- гейты: Storybook **39/39** (axe error), lint (js+css), typecheck, build — зелёные.

**Инкремент 4 — письменная сдача (зелёный):** `AttachmentView` + `AttachmentItem`/`AttachmentList` (превью, состояния processing/uploading/ready/failed/queued, переупорядочивание кнопками вверх/вниз с клавиатуры, поворот, удаление, повтор); `SubmissionComposer` (текст + до 10 фото, объяснение camera/files и лимита, общий размер, автосохранение черновика, офлайн-очередь, закрытый приём, «устную можно письменно»); `SubmissionReceipt` (время клиента+сервера, идемпотентность). `Product/Submission` stories + interaction-тесты (ввод, переупорядочивание страниц, повтор загрузки).

**Инкремент 5 — результат, тред, аннотации (зелёный):** `VerdictPanel` (вердикт + комментарий; human/AI по-разному, ИИ не спутать с преподавателем); `AttemptTimeline` (последний вердикт сразу, история раскрывается, без «номера попытки» и обвинительного тона); `FeedbackThread`/`ThreadMessage`/`FeedbackAttention` (автор/время/канал; асимметричная видимость как permission state; индикатор непрочитанного); `reaction`-registry + `ReactionPicker`/`ReactionChip` (легаси-реакции 0/100/200/300 с видимостью: ученик скрыт от учителя/виден admin, внутренняя учителя скрыта от ученика); `AnnotationOverlay` (перо/выделение/нумерованные комментарии над неизменяемой работой). `Product/Feedback` stories + interaction-тесты (выбор реакции, раскрытие истории, комментарий-аннотация).

**Инкремент 6 — Telegram-rich новости (зелёный):** `TelegramPostView` + `TelegramRichPost` — entities (bold/italic/underline/strike/code/link/spoiler со снятием размытия), цитаты, math через hook `renderMath`, альбом, плейсхолдеры видео/документа, forwarded/source attribution; варианты card/detail и превью surface pwa/telegram; редакционные состояния (изменено в источнике / локальная правка / удалено / ошибка доставки / скрыто). `Product/News` stories + interaction-тест (раскрытие спойлера).

**Инкремент 7 — connectivity (зелёный):** `ConnectionBanner` (online ненавязчив; offline/reconnecting объясняют влияние на действие; conflict — не исчезающий toast, требует решения); `SyncIndicator` (счётчик очереди → outbox, тихо когда нечего слать); `UpdatePrompt` (не рушит черновик); `PushPermissionCard` (объясняет категории до системного запроса, уважает отказ). `Product/Connectivity` stories + interaction-тесты.

**Инкремент 8 — рабочее место Staff (зелёный):** `ReviewQueue` (плотная, сортировка задача/ожидание/группа/ученик, list/fast, счётчик+возраст, занятая работа с именем и disabled, перепроверка); `ReviewLock` (аренда held/busy/lost); `VerdictActions` (из registry лучший→худший, кнопки + цифры, `1`=«+», легенда, не срабатывает в поле); `ReviewFeedbackForm` c `ReviewCommentGuard` (вердикт ниже «+» без комментария — подтверждение, не блок) и внутренней `ReactionPicker`; `ThreePaneReview`; `DenseDataTable` (sticky, сортировка, выбор, keyboard); `MetadataGrid` (правка ячеек, вставка TSV, dry-run, undo); админ-поверхности `PublicationControl`, `LatexUpload`, `MissingAssetsFlow`, `BroadcastComposer`, `ClassroomPlanner` (select/move без DnD-зависимости), `SosQueue` (отдельно от очереди вердиктов). `Product/Review`, `Product/Staff data`, `Product/Staff admin` stories + interaction-тесты (сортировка, «+» цифрой, guard, публикация, рассылка, SOS, выбор/сортировка таблицы, dry-run метаданных).

**Инкремент 9 — прогресс (зелёный):** зависимость `@visx/scale` (из каталога); `DistributionViolin` (гауссова KDE, медиана, маркер своего результата словами «выше среднего»), `TrendWithBand` (линия + доверительная полоса) — обе shape-first, не по цвету, с табличным эквивалентом в `<details>`; `StudentProgress` — словами («3 задачи зачтено»), спокойный streak относительно своей истории, без leaderboard/percentile/красных провалов, распределение по группе спрятано за раскрытием (не навязывается), пустое состояние. `Product/Progress` stories + interaction-тесты.

**Итог Phase 4:** гейты зелёные — Storybook **72/72** (axe error), lint (js+css), typecheck, build. Ждёт приёмки владельцем математического чтения, submission, review workspace, news и dense grid (см. gate в `04-product-components.md`). Затем Phase 5 — страницы, начиная со Student «Сейчас» mobile-light. Visual baselines обновляются после первой реальной страницы.

## Решения итогового продуктового опросника — 24 июля 2026

- Первый рабочий корпус: занятия 39–41 сезона 2025–2026, все три уровня; сначала полный online flow. Print, быстрый очный ввод, Staff→Telegram и AI-интеграция — следующая версия.
- Clock skew больше часа помечается для диагностики. Одинаковый idempotency key с другим payload не перезаписывает операцию и требует нового ключа после явного действия.
- На один verdict разрешена одна внутренняя teacher reaction и одна student reaction; обе меняются/удаляются в течение часа.
- Отдельного dispute/«вернуть на доработку» workflow в v1 нет: состояние интерфейса выводится из актуального registry verdict. `REJECTED_ANSWER` остаётся отрицательным результатом после перепроверки.
- Hint reveal хранится как служебное методическое событие и в v1 не показывается отдельной строкой ролям.
- Причина abandon не хранится; unsent teacher comment/annotation draft сохраняется локально.
- Family self-check удалён из требований. Family видит полный student-visible thread/evidence, меняет level/mode и получает недельный итог без сравнения с группой.
- Полный набор решений и границ находится в `../development-plan/01-decisions-and-boundaries.md`; компонентные и page-требования синхронизированы в `04-product-components.md`, `05-pages-and-flows.md` и `07-acceptance-checklist.md`.

## Оставшийся инженерный follow-up

- После фиксации math corpus проверить subset/форматы KaTeX fonts и повторно измерить precache.
