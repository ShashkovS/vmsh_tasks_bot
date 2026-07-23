# Фаза 3. UI primitives

## Правило слоя

`packages/ui` не знает о задаче, уроке, ученике или API. Компоненты построены поверх Base UI и semantic tokens, экспортируют ref/props, поддерживают controlled/uncontrolled режим там, где это предусмотрено primitive, и не ломают native semantics.

## Обязательный набор

### Actions и inputs

- Button: default/secondary/outline/ghost/destructive/link, compact/default/large/icon; loading не меняет ширину и объявляется assistive technology.
- Input, Textarea: label/description/error через Field; prefix/suffix только когда не ухудшают доступность.
- Field/Label: required, optional, hint, validation, disabled, read-only, horizontal staff arrangement.
- Checkbox, Switch: indeterminate для checkbox, ясная разница action vs immediate setting.
- Select: single selection, groups, long labels, keyboard search; native fallback обсуждается для mobile.

### Overlays

- Dialog: подтверждение/форма, initial focus, destructive confirm, async pending, escape/close policy.
- Drawer: Base UI Drawer для mobile navigation/details и жеста закрытия; обычный modal без swipe остаётся Dialog.
- Popover, Tooltip, Dropdown Menu: keyboard/pointer parity, collision handling; Tooltip никогда не содержит обязательную информацию.
- Toast на Base UI: success/error/offline/update; persistent errors имеют действие и не исчезают слишком быстро. Sonner не используется.

### Structure и data

- Tabs: URL-связываемые в product layer, keyboard arrows, overflow strategy.
- Accordion: правильные headings, multiple/single, решение/подсказка не раскрываются неожиданно.
- Badge: status/tag/level; shape может быть pill, текст обязателен.
- Card: минимальная структурная оболочка, не обязательный wrapper всего контента.
- Table: caption/header/sort affordance, horizontal overflow, compact density, empty/loading rows.
- Separator, Skeleton.

Дополнить фундамент необходимыми composable primitives: Alert, Progress, Radio Group, Toggle Group, Scroll Area, Breadcrumb, Pagination, Command/Combobox только если они нужны product components; не раздувать библиотеку «на всякий случай».

## Состояния каждого компонента

Проверить default, hover, active, focus-visible, disabled, read-only, loading, invalid, high contrast, light/dark и long Russian content. Для overlay также open/closed, edge collision, scroll, nested trigger и mobile keyboard. Иконка без текста получает русское accessible name.

Validation появляется после submit или понятного завершения поля, не на первом символе. Error сохраняет введённое значение и предлагает действие. Disabled не используется вместо объяснения — product layer рядом сообщает условие доступности.

## Form composition

Установить один контракт IDs/`aria-describedby` для label, hint и error. Required marker имеет текстовое значение. Form actions располагаются предсказуемо; на mobile важное действие доступно рядом с текущим контекстом, но sticky bar не закрывает системную клавиатуру или нижнюю навигацию.

## Iconography

Lucide — единственный набор UI icons. Стандартный stroke и размеры задаются tokens. Иконка дополняет текст и редко заменяет его. Brand/product icons — отдельные собственные SVG и не смешиваются с Lucide exports.

## Story requirements

У каждого primitive:

- `Overview`, `Variants`, `States`, `Dark`, `Long content`, `Keyboard/Interaction`;
- Student touch и Staff compact examples;
- русский текст, реальные ошибки и loading duration;
- addon-a11y без violations;
- play function для значимого поведения: Dialog focus/close, menu keyboard, form validation, tabs/accordion, toast action.

Не дублировать десятки stories, если одна хорошо подписанная matrix проверяет то же самое. Но скрытые интерактивные состояния должны быть доступны тесту.

## Gate

Принимаются visual consistency, API composition, keyboard/focus, density и отсутствие raw colors/domain imports. Только после этого product components могут опираться на primitives как стабильный слой.
