# Фаза 6. Storybook и тестирование

Индекс `этап разработки → компонент → story source → Storybook URL` находится в [`development-plan/18-design-implementation-map.md`](../development-plan/18-design-implementation-map.md); переименование story обновляет оба документа в одном изменении.

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
- active/allowed/forbidden group, причём `allowed_groups` покрывает чтение и сдачу;
- course verdict registry: `+ / −`, `+ / +/2 / −`, full graded scale × Student/Family/Staff;
- verdict × level × human/AI provenance × unread feedback;
- submission × network/sync;
- review × lock/verdict/comment guard/list-fast/mobile;
- task type × oral window, включая student-представление `WRITTEN_BEFORE_ORALLY`;
- reactions × role visibility без утечки hidden teacher/student data;
- AI off/pending/advisory/full reviewer/failure/escalation;
- content loading/empty/error/partial/missing asset;
- classroom catalog active/hidden/duplicate × layout inherited/materialized × plan draft/stale/confirmed;
- classroom assignment assigned/reassigning/unassigned × Student/Family/Staff visibility, включая empty group, no-room blocking incident, missing age/grade/strength, room average age/grade/strength и classroom history;
- classroom density 6/5/2 и 15-room/~200-student × group colors/`очно–распределено` × compact flex wrap;
- classroom draft clean/dirty/restored/conflict/saved × single/bulk/cross-group move;
- short/long Russian text, 200% zoom и narrow width.

## Interaction tests

Использовать `play`/`@storybook/addon-vitest` browser mode для observable behavior:

- keyboard navigation and focus restoration overlays;
- field validation and accessible error relation;
- все historical test answer families: format failure не расходует попытку, pending checker отличается от incorrect;
- scalar/fixed tuple/list/select fixtures повторяют `helpers/checkers.py`: partial input не показывает ошибку до blur/submit, затем появляется заметный `fullmatch` error; отсутствует блок «Отправится», parsed preview есть только для валидного list, `SELECT_ONE` передаёт точный русский payload;
- weekday fixture в [`Product/Test answer`](../../packages/product/src/test-answer.stories.tsx) показывает семь кнопок `пн–вс` в одну строку и проверяет выбранный видимый payload;
- photo up/down reordering, remove and final review (worker mocked at boundary);
- offline enqueue/retry/conflict;
- hint/solution conscious disclosure;
- queue claim/lost lock/verdict и досланный material/thread-version refresh перед complete;
- verdict keyboard mapping из registry, отсутствие shortcut внутри textarea, non-accepted confirmation и abandon с освобождением lock без потери local draft;
- compact internal teacher reactions: `⌘/Ctrl + Alt + 1…4` работают при фокусе в комментарии, меняют единственную выбранную реакцию, повторный chord снимает её, `AltGraph` не перехватывается;
- occupied-by-another-teacher, fast-next и возврат к выбору задачи;
- conscious hint view event и hidden-before-publication state;
- role permission для скрытых reactions и AI output; одна reaction на verdict и часовое окно replace/delete;
- TSV paste diagnostics;
- dropdown-ячейки task type/answer type принимают keyboard selection и прямоугольную TSV-вставку;
- publication interaction независимо публикует/планирует/откатывает condition, hint и solution; отдельная scheduling story оставляет `datetime-local` открытым и проверяет, что его ширина не превышает `12rem`, а правая граница не заходит в следующую ячейку;
- classroom catalog duplicate/archive/restore, materialize layout, single/bulk select, cross-group confirmation, recalculate и confirm;
- classroom fuzzy search с `ё/е`, переставленными словами и опечаткой; jump/focus найденной строки; history disclosure;
- classroom local draft восстанавливается после remount/reload simulation, очищается после receipt и сохраняется при version conflict;
- archive assigned room → Student/Family reassigning, затем новая confirmed room; Family notification control отсутствует;
- update prompt preserving draft.

Тест проверяет пользовательский результат, не внутренний class name. React Testing Library вне Storybook оставлять для редких unit-level integrations.

## MSW

Handlers группируются по contract scenario и возвращают Zod-valid fixtures. Story явно выбирает normal/delay/error/conflict. Unhandled request считается ошибкой, кроме Storybook static assets. MSW не импортируется в production entry и не используется в Playwright E2E.

## Accessibility gate

Addon a11y имеет `test: error`. Перед принятием:

- axe gate одинаково применяется к Student, Family и Staff; для Staff обязательны label, alt, корректный ARIA и контраст. Полноценный keyboard-аналог специализированного gesture/DnD не является отдельным требованием, если такой control когда-либо появится;

- axe без violations для всех основных stories;
- Student/Family flow проходит только keyboard; Staff keyboard-проверка покрывает обычные inputs/selects/dialogs и текущий classroom flow;
- focus виден в обеих темах и не закрыт sticky regions;
- status announcements не создают spam;
- dialogs/drawers имеют name и restore focus;
- charts/math/images имеют textual equivalents;
- contrast WCAG 2.2 AA, touch target и reflow проверены вручную там, где axe недостаточен.

## Visual regression

Page screenshots в Playwright — Chromium, WebKit, Firefox с фиксированными locale/timezone/reduced-motion и production Vite build/preview, а не HMR/dev CSS. Component visual checks допустимы дополнительно. Baseline обновляется только после просмотра diff; в описании change указываются принятый gate и ожидаемые области изменения. Content gate отдельно сравнивает три листка одного уровня в PWA, Telegram и PDF derivatives.

Classroom visual set фиксирует catalog active/hidden/duplicate, inherited/materialized layout, group markers/tints, `очно/распределено`, фактические 6/5/2 и плотный 15-room/~200-student вариант, stale plan, отдельные reassigning/unassigned, missing profile data, room averages возраста/класса/силы, fuzzy result, history, bulk selection, local draft states, preview/confirm и mobile Staff. Story `mobile-staff-layout` обязана показывать все три student fields и все три room averages, а не только имена/count. Ни одна story не показывает capacity, weight или drag affordance.

## Реализованный Phase 6 corpus

- Page stories: [`Pages/Student`](../../apps/student/src/pages.stories.tsx), [`Pages/Family`](../../apps/family/src/pages.stories.tsx), [`Pages/Staff`](../../apps/staff/src/pages.stories.tsx). Они покрывают основные ready flows, loading/empty/error/offline, login/reveal, validation, read-only Family, Staff verdict и classroom tab interaction.
- Component corpus: [`packages/product/src`](../../packages/product/src) и [`packages/ui/src`](../../packages/ui/src). Classroom stories `Plan local draft restored` и `Plan dense two hundred students` являются точными proof для reload и 15-room/200-row требований.
- Глобальные light/dark, density и reduced-motion controls, MSW strict handling и `a11y: error`: [`.storybook/preview.tsx`](../../.storybook/preview.tsx). Story discovery: [`.storybook/main.ts`](../../.storybook/main.ts).
- 26 июля browser-mode gate после compact internal-reaction и bounded publication-scheduler increments: **24 files / 121 stories passed**, включая addon-a11y error mode. Ручной осмотр выполнен на agent Storybook `6106` для `Pages/Student--Today`, `Pages/Staff--Review workspace`, `Pages/Staff--Classrooms`, `Product/Review--Feedback guard`, `Product/Review--Feedback reaction shortcuts` и `Product/Staff admin--Publication scheduling`; он обнаружил и закрыл ошибку horizontal Tabs в [`tabs.tsx`](../../packages/ui/src/components/tabs.tsx), подтвердил 24px compact reactions и отсутствие overlap у scheduler на desktop/narrow Staff viewport.
- Production page screenshot baseline хранится в [`e2e/__screenshots__`](../../e2e/__screenshots__) и проверяется на production Vite preview, а не на dev server. 25 июля после ручного просмотра ожидаемых изменений baseline был обновлён; повторный обычный запуск дал **36/36** E2E/visual checks в Chromium, WebKit и Firefox. Browser-mode Storybook не подменяет этот gate.

## Gate

Storybook build и addon-vitest проходят, нет a11y errors, все обязательные states доступны, initial page baselines проверены. В `STATUS.md` записываются browser/tool versions и consciously accepted exceptions с владельцем/сроком; бессрочных молчаливых исключений нет.

## Multi-course story matrix

Обязательный корпус:

- `Product/Courses--student-multiple-courses`, `--active-and-allowed-groups`;
- `Product/Staff-admin--course-and-group-catalog`, `--independent-schedules`, `--telegram-bindings`;
- `Product/Staff-data--synonym-merge-and-split`;
- `Product/Feedback--synonym-merged-timeline`;
- `Product/Review--synonym-combined-case`;
- `Product/Classrooms--multi-course-inherited-event`;
- `Product/Progress--courses-separated`;
- соответствующие `Pages/Student`, `Pages/Family`, `Pages/Staff` из [карты](../development-plan/18-design-implementation-map.md).

Interaction assertions проверяют переключение course/group, snapshot/inheritance labels, merge/split identity notice, chronology provenance, combined review target, classroom inherited counts и отсутствие group comparison в Student/Family. Unit projection suite лежит в `packages/product/src/multi-course-projection.test.ts`. Visual snapshots не обновляются до ручного owner review нового mobile-light/desktop инкремента.
