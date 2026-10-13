# Фаза 2. Brand и design tokens

## Результат

Выбранное направление переводится в три слоя: primitive → semantic → component. Product code использует только semantic/component aliases; primitive palette доступна внутри token layer и специальных showcase stories.

## Именование и размещение

CSS variables живут в `packages/ui/src/styles`, экспортируются через `@theme inline` и имеют светлые значения в `:root`, тёмные в `.dark`. Имена описывают назначение, а не оттенок: `--color-surface-raised`, не `--color-gray-50`.

Минимальный primitive layer:

- нейтральная OKLCH-шкала с предсказуемой lightness;
- один спокойный brand hue и при необходимости вторичный;
- отдельные hue families для success, warning, danger, information;
- три текущих уровня обучения, возможный четвёртый и нейтральный fallback как самостоятельные семьи;
- alpha/overlay primitives.

Semantic color layer:

- `background`, `foreground`, `muted`, `muted-foreground`;
- `surface`, `surface-subtle`, `surface-raised`, `surface-sunken`;
- `border`, `border-strong`, `border-interactive`;
- `primary`, `primary-foreground`, `secondary`, `accent`;
- `focus-ring`, `selection`, `link`, `link-visited`;
- `overlay`, `scrim`, `disabled`, `placeholder`;
- `success|warning|danger|info` + `-foreground`, `-surface`, `-border`;
- `level-a|b|c|d` + readable surface/border/foreground пары;
- task/review states: not-started, draft, queued, sent, checking, needs-work, accepted, rejected, closed;
- verdict scale: neutral/no-answer, rejected, partial-low/mid/high и solved; конкретный набор приходит из registry курса, а цвет не заменяет символ и подпись;
- feedback provenance: human teacher, AI advisory, AI verdict; AI никогда не маскируется под human author;
- unread feedback и скрытые reaction families без утечки staff-only meaning в Student/Family;
- connection states: online, reconnecting, offline, syncing, conflict;
- chart series 1–8, grid, axis, reference line;
- annotation pen/highlight/comment/selection.

Уровневые цвета не совпадают по семантике с success/error/warning или verdict scale и всегда сопровождаются short code/названием уровня. Неизвестный уровень получает нейтральный fallback. Все пары проходят contrast audit в реальном размере текста; декоративный большой текст не используется для обхода AA.

## Типографика

Определить tokens:

- UI family, reading serif, math fallback chain, mono;
- display, page title, section title, body, reading body, small, caption, label, code;
- font size, line height, weight, letter spacing и paragraph spacing как согласованные styles;
- tabular numerals для времени, статистики и таблиц;
- math inline/display size, equation spacing, equation number и long-expression overflow.

Цель: основной Student UI не менее 16 px, reading line length ориентировочно 58–72 символа на desktop, 100% ширины с безопасными полями на mobile. Staff может быть компактнее, но не мельче доступного минимума.

## Размеры и плотность

Spacing scale основана на последовательной малой единице и имеет aliases `page-gutter`, `section-gap`, `control-gap`, `reading-indent`. Не делать каждый отступ уникальным.

Student/Family touch targets минимум 44×44 CSS px; основное действие сдачи предпочтительно 48 px. Staff controls постоянно компактнее, но interactive target не менее 32 px и имеет достаточный keyboard focus. Density реализуется через component tokens/attribute, а не глобальное CSS scale.

Radius: небольшие/умеренные значения для controls/panels; pills только tags/status. Elevation применяется для overlays и действительно поднятых surfaces, не для каждой Card.

## Остальные token families

- borders: widths/styles, active/invalid/read-only;
- elevation: 0–4 с light/dark shadow tuning;
- z-index: base, sticky, navigation, popover, modal, toast;
- motion: duration instant/fast/normal/slow, standard/emphasized easing;
- icon sizes и stroke behavior;
- container widths: reading, form, app, wide staff;
- breakpoints согласованы с content, а не конкретными устройствами;
- safe-area insets, bottom-nav height, sticky header offsets;
- skeleton shimmer/neutral fallback с reduced-motion.

## Brand assets

Финализировать accessible SVG: wordmark, sign, Student/Family/Staff icons, favicon/maskable variants. SVG не содержит hard-coded theme color, если asset должен наследовать `currentColor`; многоцветные версии используют brand token mapping. Добавить текстовые правила clear space, minimum size и недопустимые трансформации.

## Stories и тесты

- primitive palette только как internal reference;
- semantic surfaces/text/borders interactive matrix в light/dark;
- level × status collision matrix;
- level × verdict × human/AI provenance collision matrix;
- typography specimen с русским математическим текстом;
- spacing/radius/elevation/motion specimens;
- Student vs Staff density на одинаковой форме;
- forced colors/reduced motion notes;
- automated contrast assertions для ключевых пар, если tooling позволяет, плюс a11y browser check.

## Gate

Владелец принимает точные brand assets, font strategy, light/dark palettes, level colors, density и motion. После gate изменение базового token требует записи решения; UI primitives не должны вводить собственные raw значения для обхода tokens.
