# Фаза 6. Storybook и тестирование

## Информационная архитектура Storybook

Рекомендуемый порядок:

1. `Foundations/Brand`, `Colors`, `Typography`, `Spacing`, `Elevation`, `Motion`, `Density`;
2. `Primitives/*`;
3. `Content/Math document`, `Figures`, `News`;
4. `Student/*`, `Family/*`, `Staff/*` product components;
5. `Patterns/Connectivity`, `Forms`, `Loading-Empty-Error`, `Layouts`;
6. `Pages/Student`, `Pages/Family`, `Pages/Staff`;
7. временный `Exploration/*`, удаляемый/архивируемый после gate.

Каждая story детерминирована: фиксированные dates, locale, IDs, media и network handlers. Она не обращается к production API.

## Global controls

- theme: light/dark;
- product/audience where reusable;
- density: student/family/staff;
- locale остаётся ru на этом этапе;
- reduced motion simulation;
- viewport presets проекта.

Theme decorator меняет реальный `.dark`, background и color scheme. Не имитировать dark одной карточкой внутри светлой страницы.

## State matrices

Обязательные matrices:

- theme × semantic colors × contrast;
- level × status, чтобы level не выглядел verdict;
- density × primitives/forms/tables;
- task state × deadline phase;
- submission × network/sync;
- review × lock/verdict;
- content loading/empty/error/partial/missing asset;
- short/long Russian text, 200% zoom и narrow width.

## Interaction tests

Использовать `play`/`@storybook/addon-vitest` browser mode для observable behavior:

- keyboard navigation and focus restoration overlays;
- field validation and accessible error relation;
- test answer entry/format failure;
- photo reorder/remove and final review (worker mocked at boundary);
- offline enqueue/retry/conflict;
- hint/solution conscious disclosure;
- queue claim/lost lock/verdict;
- TSV paste diagnostics;
- classroom keyboard move;
- update prompt preserving draft.

Тест проверяет пользовательский результат, не внутренний class name. React Testing Library вне Storybook оставлять для редких unit-level integrations.

## MSW

Handlers группируются по contract scenario и возвращают Zod-valid fixtures. Story явно выбирает normal/delay/error/conflict. Unhandled request считается ошибкой, кроме Storybook static assets. MSW не импортируется в production entry и не используется в Playwright E2E.

## Accessibility gate

Addon a11y имеет `test: error`. Перед принятием:

- axe без violations для всех основных stories;
- весь flow только keyboard;
- focus виден в обеих темах и не закрыт sticky regions;
- status announcements не создают spam;
- dialogs/sheets имеют name и restore focus;
- charts/math/images имеют textual equivalents;
- contrast WCAG 2.2 AA, touch target и reflow проверены вручную там, где axe недостаточен.

## Visual regression

Page screenshots в Playwright — Chromium, WebKit, Firefox с фиксированными locale/timezone/reduced-motion. Component visual checks допустимы дополнительно. Baseline обновляется только после просмотра diff; в описании change указываются принятый gate и ожидаемые области изменения.

## Gate

Storybook build и addon-vitest проходят, нет a11y errors, все обязательные states доступны, initial page baselines проверены. В `STATUS.md` записываются browser/tool versions и consciously accepted exceptions с владельцем/сроком; бессрочных молчаливых исключений нет.
