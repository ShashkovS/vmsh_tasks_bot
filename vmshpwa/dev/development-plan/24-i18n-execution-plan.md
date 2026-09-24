# RU → EN localization: step-by-step execution plan

Status: P3 was implemented locally on 2026-09-24 and its phase gates passed. P4–P8 remain implementation instructions; this document remains the authoritative procedure for them.

This is an English-language execution companion to [24-i18n.md](24-i18n.md), intended for an agent that needs explicit, small, verifiable tasks. Follow the existing architecture; do not invent a replacement translation system. Finish one batch before starting another.

Authoritative references:

- [ADR 0004](../../../adr/0004-pwa-internationalization.md): architecture, language preference and exclusions.
- [Developer rules](../../docs/i18n.md): macros, catalogs and formatting.
- [English glossary](../../docs/i18n-glossary.md): vocabulary and writing style.
- [Phase plan](24-i18n.md): P0–P8, completion evidence and performance limits.
- [Workspace instructions](../../AGENTS.md), plus the applicable nested `AGENTS.md` before editing an app, package or E2E test.
- [Development status](STATUS.md) and [design-system status](../design-system/STATUS.md): record progress in both.

## 1. What exists now: inspected baseline, not an assumption

Repository revision inspected: `7fbbeb15`. The worktree was clean before this documentation task. Recheck the revision and worktree before implementation; this snapshot will become outdated.

### 1.1 Implemented foundations

P0 and P1 are recorded as implemented locally. The inspected source agrees with the main architecture:

- Lingui catalogs and compilation are configured in [lingui.config.ts](../../lingui.config.ts) and [vite-i18n.ts](../../vite-i18n.ts).
- [packages/i18n](../../packages/i18n/src/index.ts) provides activation, cookies, React context and cached formatters.
- Applications merge their own catalog with dependency catalogs in `apps/<app>/src/i18n/catalog-{ru,en}.ts`.
- Russian is the default. Account language is saved through `PUT /{audience}/api/v1/auth/locale`; changing it sets the cookie and reloads the page.
- The account locale migration already exists: `0098.pwa_account_locale`. Do not create another locale column or another language endpoint.
- App shell, sign-in, navigation, language controls, UI primitives and selected update/connection components have been translated.
- Backend request language and error translation already exist in [helpers/pwa/i18n.py](../../../helpers/pwa/i18n.py) and [middleware.py](../../../apps/pwa_api/middleware.py).
- [i18n-scopes.json](../../i18n-scopes.json) covers only the completed areas. It is deliberately not a list of the whole product yet.

### 1.2 Actual catalog counts

Counts below are catalog entries, not distinct phrases across all packages and not the percentage of the product translated. Frontend counts were read with Lingui's own PO formatter; backend counts with its existing Python reader.

| Catalog owner               | Entries currently extracted | Nonempty English translations |
| --------------------------- | --------------------------: | ----------------------------: |
| `packages/ui`               |                           4 |                             4 |
| `packages/content`          |                           0 |                             0 |
| `packages/product`          |                          14 |                            14 |
| `packages/app-shell`        |                         143 |                           143 |
| `apps/student`              |                          43 |                            43 |
| `apps/family`               |                          34 |                            34 |
| `apps/staff`                |                          44 |                            44 |
| `apps/landing`              |                           1 |                             1 |
| Frontend total              |                         283 |                           283 |
| `helpers/pwa/locales/en.po` |                         536 |                            17 |

Most remaining frontend text has **not been wrapped/extracted**. An empty content catalog does not mean that content-related UI has no labels to translate.

A raw Cyrillic scan of production `.ts`/`.tsx`, excluding tests, stories and generated route trees, found the following candidate areas. Counts include already localized strings, comments and legitimate Russian data; they are **not counts of missing translations**.

| Area           | Files with Cyrillic | Lines containing Cyrillic |
| -------------- | ------------------: | ------------------------: |
| Staff          |                  78 |                     2,085 |
| Student        |                  23 |                       491 |
| Family         |                  12 |                       238 |
| Landing        |                   2 |                        13 |
| Shared product |                  72 |                       894 |
| App shell      |                  13 |                       151 |
| Content        |                   5 |                        15 |
| Contracts      |                   5 |                        12 |
| Offline        |                   1 |                         3 |

### 1.3 Checks performed for this plan

- `cd vmshpwa && node scripts/i18n-check.mjs --no-extract`: passed coverage of currently declared frontend scopes and catalog-merge checks. **Extraction synchronization was not checked**, despite the script's generic success message saying “in sync”.
- `.venv/bin/python -m vmshpwa.scripts.backend_i18n check`: failed because the backend catalog is stale.
- Current extraction finds **547 backend keys**, versus 536 in the file: 11 missing keys, no removed keys. There are also two dynamic error-message expressions outside completed scopes.
- No full build, unit, Storybook, E2E or performance run was performed for this documentation-only task. Historical P0/P1 pass counts are not current test results.
- Shell tools reported Node `v26.9.0`, Python `3.14.3`, and pnpm `12.5.1`. The repository requires pnpm `11.15.1`. Resolve the pnpm mismatch before invoking the normal pnpm/Make checks; do not upgrade the lockfile to accommodate the wrong executable.

Missing backend source keys at this revision:

```text
Markdown должен быть текстом
Блок занятия не найден
Блок уже изменился. Обновите страницу.
Время публикации некорректно
Картинка должна быть PNG, JPEG или WebP
Не удалось безопасно сохранить картинку
Не удалось обработать блок занятия
Не удалось разобрать форму картинки
Проверьте revision
Проверьте содержимое или настройки публикации
Тело запроса должно быть JSON-объектом
```

### 1.4 Important implementation gaps and traps

1. [push_delivery.py](../../../helpers/pwa/push_delivery.py) builds Russian title/body strings. [notification_deliveries.py](../../../db_methods/pwa/notification_deliveries.py) joins `auth_accounts` when claiming deliveries but does not select its locale. Translating only the frontend notification card cannot translate native push notifications.
2. [models/pwa/submissions.py](../../../models/pwa/submissions.py) produces default feedback alongside configurable, author-written feedback. [db_methods/pwa/submissions.py](../../../db_methods/pwa/submissions.py) persists feedback and response payloads. Translation must happen when constructing the PWA response, without changing stored history or custom text.
3. Reaction and verdict registries contain module-level Russian labels. `verdict-registry.ts` also materializes derived scales at module evaluation. Replacing labels with getters alone is insufficient if a spread has already copied the getter result into a static object.
4. [Staff pages.tsx](../../apps/staff/src/pages.tsx) contains multiple feature areas. Do not declare that entire file translated after handling one component.
5. [nginx configuration](../../deploy/nginx/vmshpwa.conf.template) contains Russian maintenance JSON outside the Python middleware. Python localization does not affect it.
6. The existing codemod can introduce getters; the preferred new static-map pattern is `msg` descriptors resolved during rendering. Review codemod output, including callers and derived objects.
7. `docs/i18n.md` recommends simple placeholder identifiers and mentions `lingui/no-expression-in-message`; the actual [ESLint configuration](../../eslint.config.js) currently turns that rule **off**. Still use simple named variables. Do not assume the linter will enforce this recommendation.
8. The frontend checker may **rewrite PO files** while checking synchronization. It is not a read-only command unless `--no-extract` is used.
9. The backend extractor only recognizes literal arguments to `N_`, `_`, and `PwaApiError(message=...)`. It does not discover every string sent in a successful JSON response or a diagnostic list.

## 2. Fixed decisions: do not ask the owner to decide these again

### 2.1 Languages and storage

- This execution document is in English.
- Product source messages remain **Russian** in TypeScript/TSX/Python.
- English translations belong in `.po` `msgstr` values.
- Use **US English**. Formatting locale is `en-US`; date presentation is month-first and time presentation uses the locale's 12-hour convention, unless a particular machine-oriented field explicitly requires another format.
- Preserve business timezones, especially `Europe/Moscow`. Language selection must never shift a class or deadline to a different instant.
- Account/device default remains `ru`. Do not infer language from the browser or OS.
- Follow the existing save → cookie → page reload language-switch flow.
- Do not introduce JSON dictionaries, a second i18n library, manually assigned English message IDs, or `locale === 'en' ? ... : ...` throughout the UI.
- Brand spelling is **VMSh 179** in English.

### 2.2 Translation style

Use the [glossary](../../docs/i18n-glossary.md) before translating any batch. Examples:

| Russian          | Use in English     | Avoid                                               |
| ---------------- | ------------------ | --------------------------------------------------- |
| задача           | problem            | task, exercise as arbitrary synonyms                |
| занятие          | class              | lesson when it means the scheduled meeting          |
| урок             | lesson             | class when it means the published set of statements |
| листок           | worksheet          | leaflet                                             |
| условие          | statement          | condition                                           |
| личный кабинет   | account            | personal cabinet                                    |
| на проверке      | under review       | on checking                                         |
| письменная сдача | written solution   | written surrender                                   |
| устный приём     | oral session       | oral reception                                      |
| войти / выйти    | Sign in / Sign out | Log in in one screen and Sign in in another         |
| организаторы     | organizers         | organizers team as an invented product name         |

Use sentence case: `Notification settings`, not `Notification Settings`. Use short button verbs: `Save`, `Cancel`, `Retry`, `Submit`. Use neutral `you`. Preserve the meaning, severity and requested action of an error. Do not add blame, praise, policy promises or capabilities absent from the Russian source. Keep labels consistent with the UI users navigate to.

Translate complete sentences, not independent fragments joined in Russian word order. Preserve names, URLs, identifiers, examples of required input and placeholder semantics. Use “problem” for a mathematics problem; a technical background job can still be a “task” when that is its actual meaning.

### 2.3 Exact boundary between UI and data

| String kind                                                                | Action                                                 |
| -------------------------------------------------------------------------- | ------------------------------------------------------ |
| Button, heading, menu, form label, hint, tooltip                           | Localize                                               |
| `aria-label`, `alt`, screen-reader-only text, toast, confirmation          | Localize                                               |
| Loading, empty, offline, validation, permission, retry states              | Localize                                               |
| Application-owned status/verdict/reaction display label                    | Localize by stable status/ID; do not translate the ID  |
| Error message from PWA API or WebSocket                                    | Localize at the PWA boundary                           |
| Web Push generated title/body                                              | Localize for the recipient                             |
| Course/group names, people, room names entered as data                     | Preserve                                               |
| Lesson statements, answers, hints, solutions, compiled lesson labels       | Preserve                                               |
| News/banners/comments/messages written by people                           | Preserve                                               |
| Custom congratulation/wrong-answer/validation text in lesson configuration | Preserve                                               |
| Default application feedback                                               | Localize on read, with safe identification of defaults |
| XLSX sheet/column names, TSV protocol headers, legacy print JSON keys      | Preserve the format                                    |
| Stable API codes, enum values, URL paths, storage keys, analytics names    | Preserve                                               |
| Telegram message templates and Telegram delivery text                      | Preserve Russian                                       |
| UI controlling Telegram bindings or publishing                             | Localize the controls, not the delivered message       |
| Application name in the install manifest                                   | Preserve, per the existing scope exclusion             |
| Test/Storybook fixtures and Russian assertions                             | Preserve unless a test intentionally targets English   |
| Logs and developer comments                                                | No translation required for this task                  |

Example: a label reading `Group` can be English while its value `Начинающие` stays Russian. A menu action `Copy statement` is UI; the copied mathematical statement is content. The label `Sheet` can be English while the sheet identifier `Задачи` must remain exact.

## 3. Work organization and progress records

### 3.1 Unit of work

A batch should normally contain 3–8 related production files plus their catalogs/tests. A large page of hundreds of lines may be a batch by itself. Work sequentially unless the user explicitly requests delegation. Do not start with a codemod over the entire repository.

For every batch, record:

```text
Batch ID: P2.1
State: not started / in progress / blocked / verified
Source revision:
Files inspected:
Files changed:
UI surfaces and states covered:
Data/content exclusions, with reason:
New or changed glossary terms:
Catalog entries translated:
Scope globs added:
Checks run and outcomes:
English visual evidence:
Known failures and evidence that they predate the batch:
Next exact step:
```

Add the batch record to `24-i18n.md` under the corresponding phase or a linked phase report. Keep `STATUS.md` and `../design-system/STATUS.md` concise and link to that record. Mark a phase complete only after its entire checklist and gates pass. A page having English headings is not a completed phase.

### 3.2 Before the first implementation batch

Run from the repository root:

```sh
pwd
git status --short
git rev-parse --short HEAD
node --version
pnpm --version
```

Then:

1. Read the applicable `AGENTS.md` files.
2. Save the initial worktree state in the batch record; preserve unrelated edits.
3. Select the repository-required pnpm 11.15.1 through the existing local toolchain/package-manager setup. Check the version again. If it is unavailable, report the exact setup blocker; do not regenerate dependencies with pnpm 12.
4. Inspect `Makefile` and `vmshpwa/package.json` before relying on a command.
5. Run the normal i18n extraction with the correct toolchain. This repairs synchronization; it does not translate anything by itself.
6. Review the 11 missing backend entries and any newly discovered differences. Treat a changed current baseline as current evidence, not as an error in this document.
7. Translate those 11 application-owned diagnostics as a small preliminary catalog batch, then run the i18n gate. Do not mark the whole content API as covered just for translating these entries.
8. Establish current lint/typecheck/unit/build results once. Do not inherit the old P0 “9 lint remarks” or “10 backend failures” as a permanent exemption.
9. Record pre-existing failures by test/file and error, with a current baseline reproduction where needed.

Do not run `python main.py`, production migrations, Google imports or Telegram polling. If a browser session is needed, use only `make pwa-agent-*` servers and the isolated fixture setup documented in the Makefile. E2E uses the repository's isolated runner. Do not use human/production accounts or databases.

## 4. Find all strings before editing a batch

### 4.1 Frontend discovery commands

All commands in this subsection run from the repository root. `rg` returning status 1 simply means no matches.

```sh
# Production source files; generated code and test fixtures are separate work.
rg --files vmshpwa/apps vmshpwa/packages \
  -g '*.ts' -g '*.tsx' \
  -g '!*.test.ts' -g '!*.test.tsx' \
  -g '!*.stories.ts' -g '!*.stories.tsx' \
  -g '!routeTree.gen.ts' -g '!**/locales/**'

# Candidate Cyrillic, including both wrapped and unwrapped strings.
rg -n '[А-Яа-яЁё]' vmshpwa/apps vmshpwa/packages \
  -g '*.ts' -g '*.tsx' \
  -g '!*.test.ts' -g '!*.test.tsx' \
  -g '!*.stories.ts' -g '!*.stories.tsx' \
  -g '!routeTree.gen.ts' -g '!**/locales/**'

# Less visible UI and API message presentation.
rg -n 'aria-label|aria-description|placeholder|title=|alt=|sr-only|toast|confirm\(|alert\(|document.title|setCustomValidity|\.message|\.feedback|reactionLabel' \
  vmshpwa/apps vmshpwa/packages -g '*.ts' -g '*.tsx' \
  -g '!*.test.*' -g '!*.stories.*' -g '!routeTree.gen.ts'

# Formatting and hand-written grammatical logic.
rg -n 'ru-RU|toLocale(Date|Time)?String|Intl\.|plural|declen|% 10|% 100|localeCompare|toLocaleLowerCase' \
  vmshpwa/apps vmshpwa/packages -g '*.ts' -g '*.tsx' \
  -g '!*.test.*' -g '!*.stories.*' -g '!routeTree.gen.ts'
```

Repeat the Cyrillic search with the batch's exact directory/file arguments. Do not treat every hit as UI. Comments, regular expressions, protocol values and fixtures can legitimately contain Cyrillic.

For each page:

1. Read its route module.
2. Follow imports to the actual page component. A route can contain no text while the page contains hundreds of strings.
3. Follow imports into `@vmsh/product`, `@vmsh/content` and `@vmsh/app-shell`.
4. Inspect constants, helpers, hooks and error mapping functions used by the page.
5. Inspect request clients and response fields shown verbatim to users.
6. Inspect all conditional branches: initial/loading/empty/error/success, open dialogs, tooltips, narrow-screen controls and disabled-state explanations.
7. Inspect strings already in English or consisting only of Latin characters: the Cyrillic rule cannot identify those as hard-coded UI.
8. Record where every candidate belongs: UI → macro; data → unchanged; technical → unchanged; ambiguous → investigate producer and consumer.

Do not scan only `.tsx`: status maps, notifications, date helpers and validation logic often live in `.ts`.

### 4.2 Backend discovery commands

```sh
rg -n '[А-Яа-яЁё]' apps/pwa_app.py apps/pwa_api helpers/pwa models/pwa db_methods/pwa -g '*.py'
rg -n 'PwaApiError|message=|feedback|reaction_label|label|title|body|warning|diagnostic' \
  apps/pwa_api helpers/pwa models/pwa db_methods/pwa -g '*.py'
rg -n 'PUSH_COPY|_payload|claim_deliveries|auth_accounts' \
  helpers/pwa/push_delivery.py db_methods/pwa/notification_deliveries.py
rg -n '[А-Яа-яЁё]|503' vmshpwa/deploy/nginx/vmshpwa.conf.template
```

Trace a visible backend string in both directions: where it is produced/stored, and where it is serialized/displayed. Search successful responses, warning lists and fallback names as well as exceptions. The middleware only translates `PwaApiError.message`; it does not translate arbitrary JSON fields.

Inspect dynamic errors through the existing extractor without mutating catalogs:

```sh
.venv/bin/python - <<'PY'
from vmshpwa.scripts.backend_i18n import extract, python_sources
for item in extract(python_sources()).dynamic:
    print(f'{item.origin}:{item.line}: {item.kind}')
PY
```

This is a repository-local diagnostic. Normal extraction/checking should use the Make targets.

### 4.3 Build a small inventory

Before changing a batch, write a table in its progress report:

| File/component         | UI states                       | Catalog owner | Data exclusions    | Backend producer  | Verification                          |
| ---------------------- | ------------------------------- | ------------- | ------------------ | ----------------- | ------------------------------------- |
| `family-home-page.tsx` | loading, empty, loaded, failure | Family        | child/course names | family course API | RU/EN component + English route smoke |

Use real inspected files. Add discovered dependencies immediately. Avoid an inventory made only from guesses about filenames.

## 5. Frontend implementation recipes

Examples below show the intended pattern. Adapt the surrounding types and props to the actual component. Do not paste an example as a new abstraction when a local edit suffices.

### 5.1 Static JSX

```tsx
import { Trans } from '@lingui/react/macro'

<h2><Trans>Настройки уведомлений</Trans></h2>
<Button><Trans>Сохранить</Trans></Button>
```

Wrap the human-readable phrase, not an entire component tree. Preserve semantics, event handlers, class names and layout. Do not wrap only a variable or nest `<Trans>` inside `<Trans>`.

### 5.2 Attributes, callbacks and conditional labels

```tsx
import { t } from '@lingui/core/macro'

function SettingsForm({ saving }: { saving: boolean }) {
  return (
    <Button aria-label={t`Сохранить настройки`}>{saving ? t`Сохраняем…` : t`Сохранить`}</Button>
  )
}

function confirmDeletion() {
  return window.confirm(t`Удалить черновик?`)
}
```

Translate both branches of a conditional, the accessible label and any toast produced by the action. Keep `t` evaluation inside a function. Do not import `t` from a different library or replace the current reload mechanism with a new hook-based language flow.

### 5.3 Interpolation

```tsx
const name = child.displayName
const number = lesson.number

return (
  <p>
    <Trans>
      Занятие {number} для {name}
    </Trans>
  </p>
)
```

Equivalent string-only pattern:

```tsx
const name = child.displayName
const heading = t`Прогресс: ${name}`
```

- Give expressions simple local names before inserting them into a message.
- Translate the entire phrase, including punctuation that belongs to it.
- Do not translate the value of `name`.
- Do not use `t(variable)` as a way to translate arbitrary strings: extraction needs a statically visible source message.
- Do not concatenate separately translated grammatical fragments.

### 5.4 Rich text with links or emphasis

```tsx
<p>
  <Trans>
    Откройте <a href="/student/profile">профиль</a>, чтобы изменить настройки.
  </Trans>
</p>
```

Keep the sentence as one message so English can move the linked phrase if needed. In the extracted PO entry, preserve numbered rich-text placeholders such as `<0>...</0>` exactly. Do not insert raw HTML into translated strings or use `dangerouslySetInnerHTML` for localization.

### 5.5 Plural forms

```tsx
import { Plural } from '@lingui/react/macro'
import { plural } from '@lingui/core/macro'

;<Plural value={count} one="# задача" few="# задачи" many="# задач" other="# задачи" />

const summary = plural(count, {
  one: '# задача',
  few: '# задачи',
  many: '# задач',
  other: '# задачи',
})
```

Translate the generated ICU message into English using `one` and `other`, for example:

```po
msgid "{count, plural, one {# задача} few {# задачи} many {# задач} other {# задачи}}"
msgstr "{count, plural, one {# problem} other {# problems}}"
```

The actual generated variable name may differ; preserve it rather than copying this example's `count`. Preserve explicit `=0` branches if the source has a special zero message. Test 0, 1, 2, 5, 11 and 21. Do not keep a `% 10`/`% 100` Russian plural helper to select English words.

### 5.6 Module-level maps and registries

Preferred new pattern:

```tsx
import { msg } from '@lingui/core/macro'
import { useLingui } from '@lingui/react'

const statusMessages = {
  pending: msg`На проверке`,
  done: msg`Проверено`,
}

function StatusLabel({ status }: { status: keyof typeof statusMessages }) {
  const { i18n } = useLingui()
  return <span>{i18n._(statusMessages[status])}</span>
}
```

If an existing public type requires `label: string`, do not silently change it to a descriptor. Keep an internal descriptor map and resolve it in a function that returns the existing view model. Inspect all consumers before changing a registry interface.

For verdicts and reactions:

1. Preserve stable IDs, values, ordering, weights, tones, symbols and visibility rules.
2. Keep source labels as extractable descriptors.
3. Resolve labels when constructing the displayed view model after locale activation.
4. Search for arrays created at module scope and object spreads that eagerly materialize labels.
5. Update those consumers to obtain translated view models at call/render time.
6. Test an English cold start and rendering after RU/EN activation in the same unit-test process.
7. Do not expose teacher-internal reactions while changing labels.

Existing lazy getters are not automatically a bug. Keep them if evaluation is safe and callers preserve laziness. Do not refactor all completed P1 code merely to match this preferred pattern.

### 5.7 Formatting dates and numbers

In React:

```tsx
import { useFormatters } from '@vmsh/i18n'

const { formatDateTime, formatNumber } = useFormatters()
const startsAt = formatDateTime(new Date(isoTimestamp), {
  timeZone: 'Europe/Moscow',
  year: 'numeric',
  month: 'short',
  day: 'numeric',
  hour: 'numeric',
  minute: '2-digit',
})
const totalText = formatNumber(total)
```

Outside React, the current runtime exports `formatDate`, `formatTime`, `formatDateTime`, `formatNumber`, and locale-explicit cached `dateTimeFormat` / `numberFormat`. Read [formatters.ts](../../packages/i18n/src/formatters.ts) before choosing a signature. `useFormatters()` currently exposes `formatDateTime`, not a `formatDate` method.

Preserve the old options that affect business meaning. Review hard-coded `hour12: false`: if it exists only because the old UI was Russian, use the established locale convention; if a protocol/input requires 24-hour `HH:mm`, keep that machine format. Do not localize an `<input type="date">` value away from ISO or change stored timestamps.

Keep Russian name sorting and search normalization on `'ru'`. A `localeCompare(..., 'ru')` hit is not an instruction to change it to English.

### 5.8 High-volume lists

In live marking, review queues and directories:

- Compute labels in row/view-model functions or at an appropriate memoized boundary.
- Prefer a translated string over an additional `<Trans>` component in every cell.
- Use cached `@vmsh/i18n` formatters.
- Do not construct a new `Intl.*` formatter for each cell.
- Do not add repeated catalog loading or activate a locale during rendering.
- Ensure memoized results do not freeze labels before locale activation. Test cold startup and locale-sensitive tests.

### 5.9 Using the existing codemod safely

Run from `vmshpwa/`, using explicit filenames:

```sh
node scripts/i18n-codemod.mjs --dry apps/family/src/family-home-page.tsx
node scripts/i18n-codemod.mjs apps/family/src/family-home-page.tsx
```

Then review the entire diff. Resolve every `MANUAL` item. Check data literals, `value`/`defaultValue`, diagnostic strings, plural logic, module getters, derived registries and formatted dates. The codemod intentionally skips some attributes and syntactic contexts; skipped does not mean “already localized”.

Quote route filenames containing `$`, for example `'apps/student/src/routes/tasks.$courseCode.$groupCode.$lessonNumber.tsx'`. Unquoted shell expansion can target the wrong path.

## 6. Catalog workflow: where translations go and what may be edited

### 6.1 Ownership

| Source file location                         | English output                                 |
| -------------------------------------------- | ---------------------------------------------- |
| `vmshpwa/apps/family/src/**`                 | `vmshpwa/apps/family/src/locales/en.po`        |
| `vmshpwa/apps/student/src/**`                | `vmshpwa/apps/student/src/locales/en.po`       |
| `vmshpwa/apps/staff/src/**`                  | `vmshpwa/apps/staff/src/locales/en.po`         |
| `vmshpwa/apps/landing/src/**`                | `vmshpwa/apps/landing/src/locales/en.po`       |
| `vmshpwa/packages/product/src/**`            | `vmshpwa/packages/product/src/locales/en.po`   |
| `vmshpwa/packages/content/src/**`            | `vmshpwa/packages/content/src/locales/en.po`   |
| `vmshpwa/packages/app-shell/src/**`          | `vmshpwa/packages/app-shell/src/locales/en.po` |
| `vmshpwa/packages/ui/src/**`                 | `vmshpwa/packages/ui/src/locales/en.po`        |
| PWA Python messages in the extractor's roots | `helpers/pwa/locales/en.po`                    |

A shared component's translation belongs to its shared package, even when Family is the first app using it. Do not copy its messages into every app catalog by hand.

### 6.2 Exact sequence

From the repository root:

```sh
make pwa-i18n-extract
```

Then:

1. Read the catalog diff.
2. Locate each entry using its `#:` source origins. Read the source when the meaning is not obvious.
3. Edit the English `msgstr` only. Preserve generated `msgid`, `msgctxt`, origins and comments unless a deliberate source change requires regeneration.
4. Never hand-edit generated `ru.po` translations. Include extractor-generated Russian catalog changes in the batch.
5. Preserve every interpolation variable, rich-text tag, ICU selector, escape and line break that has semantic meaning.
6. Apply the glossary and the same translation for the same concept across owners.
7. If one Russian word has different meanings, add source `context` and a translator `comment`, then extract again. Do not use the wrong English word merely to reuse an existing key.
8. Do not fill missing English with Russian just to make the gate pass.
9. Do not remove origins, mark live entries obsolete or shrink scope globs to hide failures.
10. Run extraction again and inspect for unexpected changes. A second extraction should preserve the translations and be stable.
11. Run `make pwa-i18n-check`.

Simple example:

```po
#: apps/family/src/family-home-page.tsx
msgid "Активная группа"
msgstr "Active group"
```

The entry above illustrates the file format, not a claim that this exact origin exists. Let extraction generate actual origins and message IDs.

Do not rely only on `rg 'msgstr ""'`: headers and multiline nonempty translations also use an empty first line. Use Lingui's PO parser/checker for frontend catalogs. Babel's reader works for the backend's format; in this snapshot, using it on frontend catalogs raised an error on an empty revision-date header. Do not rewrite headers just to make an unrelated ad hoc parser work.

### 6.3 Catalog merging

Existing owners are already configured. Normally no loader edit is needed. If a real new catalog owner is necessary, update all of the following together:

- `lingui.config.ts` owner list;
- that package's exports for `locales/*.po`, following an existing package;
- both `catalog-ru.ts` and `catalog-en.ts` in every consuming app;
- package dependencies where needed;
- unit-test catalog loaders and Storybook loading;
- relevant tests/build guard checks.

Do not add a UI runtime dependency to `packages/contracts` just to translate an enum or protocol value. Prefer keeping contract values stable and localizing their presentation in the consuming UI. Service workers do not have a React provider: do not import React macros into them. Prefer server-localized native push payloads and explicitly inspect any worker fallback text.

## 7. Backend implementation recipes

### 7.1 Static PWA API errors

This is already extractable and translated by middleware:

```python
raise PwaApiError(
    status=409,
    code="already_reviewed",
    message="Задача уже проверена",
)
```

Do not translate `code`. Do not wrap the already translated result a second time. Translate the corresponding backend `msgstr` and put the route in the backend scope only once all of its visible messages have been reviewed.

### 7.2 Dynamic errors

Replace this pattern:

```python
message=f"Задача {number} уже проверена"
```

with:

```python
raise PwaApiError(
    status=409,
    code="already_reviewed",
    message="Задача {number} уже проверена",
    params={"number": number},
)
```

Keep placeholder names identical in Russian and English. Preserve status, error code, permission checks and control flow. Test at least two values so an accidentally hard-coded result cannot pass.

### 7.3 Other response labels and helper messages

```python
from helpers.pwa.i18n import N_, _, translate

DEFAULT_LABEL = N_("Без названия")

# At the request presentation boundary:
label = _(DEFAULT_LABEL)

# Explicit recipient language, outside a request:
push_title = translate(recipient_locale, N_("Проверка завершена"))
```

`N_` marks a source literal without translating it. `_` uses the current request locale. `translate` uses the explicit locale. The extractor recognizes the nested `N_("...")`; a bare `translate(locale, "...")` call is not enough for extraction.

Do not translate in database write methods. Do not store locale-dependent display labels in canonical data. A lower-layer diagnostic may retain a marked source message and parameters; resolve it when the PWA adapter constructs a response. Keep Telegram consumers of the same domain data unchanged.

Python `translate` uses `str.format_map`, **not ICU plural evaluation**. Do not paste frontend ICU syntax into backend `msgstr`. Use complete number-neutral templates where suitable, such as `Проверено задач: {count}.` / `Problems reviewed: {count}.`, or explicit whole-message branches with tests. Do not add a plural engine for a single message without a separate justified design change.

### 7.4 WebSocket errors

Find the existing WebSocket localization tests and paths. Preserve the cookie-derived language at handshake and the existing error envelope. Confirm both locales and unchanged machine codes. Do not assume a successful HTTP localization test also covers WebSocket messages.

### 7.5 Stored/default text

Never run a database migration that replaces all Russian strings with English.

For each persisted label:

1. Identify its stable code/ID or provenance, the write path and every read path.
2. Distinguish application defaults from author/user-provided content.
3. Translate recognized application text at serialization/render time.
4. Preserve unknown values and user-authored text.
5. Keep stored bytes and idempotency receipts unchanged.
6. Test reading the same record as RU and EN, including a repeat request and history view.

For test-answer feedback, a naive global mapping of every `"Да, всё верно!"` is unsafe if custom content can equal that phrase. Inspect the available historical/configuration evidence. Prefer existing provenance or stable codes. If provenance cannot be recovered reliably, preserve ambiguous historical text and record a concrete blocker for that subset; ask the owner whether to accept a limited fallback or introduce a narrowly scoped provenance change. Do not silently invent a schema migration, reinterpret old author content or mark all feedback complete without evidence.

## 8. Ordered implementation batches

Paths in frontend lists below are relative to `vmshpwa/`. Backend paths are relative to the repository root. Lists identify actual starting points, not a substitute for following imports. Scope shared components in the earliest phase that needs them; later phases verify them rather than duplicating translations.

### P2 — Family, shared progress/notifications/organizers, recipient-language push

**P2.1: Family home and children.**

- Read/edit `apps/family/src/family-home-page.tsx`, `family-children-page.tsx`, relevant sections of `pages.tsx`, and their route modules.
- Cover child switching, no children, no courses, loading, failures, lesson summaries, profile/session labels not already in P1.
- Trace `family_course_routes.py` and the course response fields actually rendered here.
- Preserve child names, course/group names and user-authored text.
- Verify a Family English home screen and child screen, plus retained Russian behavior.

**P2.2: Shared progress and lesson presentation required by Family.**

- Inspect `packages/product/src/student-progress.tsx`, `progress-charts.tsx`, `activity-calendar.tsx`, `course-context.tsx`, `course-achievements.ts`, `task-list-item.tsx`, `task-type.tsx`, `level-chip.tsx`, `problem-header.tsx`, `verdict-mark.tsx`, `verdict-registry.ts`, `deadline-notice.tsx`, `worksheet-materials.tsx`.
- Inspect Family `content-page.tsx` and the `packages/content` components it renders.
- Translate UI controls around the document; preserve lesson content and compiled labels.
- Handle plural counts, date tooltips, chart accessible labels and empty legends.
- Resolve verdict-registry evaluation before claiming progress labels are English.
- Verify long English text at narrow widths and at least one plural/date case.

**P2.3: Family news, notifications and organizers.**

- Inspect `family-notifications-page.tsx`, `family-news-page.tsx` and their routes.
- Inspect `packages/product/src/notification-event-card.tsx`, `push-device-controls.tsx`, `push-permission-card.tsx`, `group-banner.tsx`, `telegram-rich-post.tsx`, and the notification/settings shared UI they import.
- Recheck already scoped `packages/app-shell/src/organizer-pages.tsx`, `push-onboarding.tsx`, `session-management.tsx`; do not assume parent route text or backend data is covered because a shared component is.
- Inspect backend `notification_routes.py`, `push_subscription_routes.py`, `organizer_question_routes.py`, `news_routes.py`, `group_banner_routes.py` for Family-visible messages.
- Translate publication controls/statuses and notification chrome, not post bodies or organizer replies.
- Verify notification permissions (unsupported, denied, enabled), preferences, no news, a news detail, organizer empty/thread/form/error states.

**P2.4: Web Push delivery, as a separate backend batch.**

1. Add `a.locale AS recipient_locale` to the delivery-claim SELECT in `db_methods/pwa/notification_deliveries.py`, following its existing account join. Do not add a query per notification or fetch the initiating actor's locale.
2. Mark all fixed strings in `helpers/pwa/push_delivery.py` using `N_`.
3. Normalize the recipient locale with fallback `ru` and pass it explicitly to `translate` while building the payload.
4. Localize every category in `PUSH_COPY`, plus special branches: classroom prefix, family lesson digest, review count, organizer reply title/body.
5. Keep user-authored group-announcement text and course/group/room names intact.
6. Preserve route, category, event ID, timestamp, truncation, silence/quiet-hours and retry behavior.
7. Read the account locale on delivery claim, so a queued notification uses the account preference current at that attempt. Record this behavior in the phase evidence.
8. Extend `pwa_tests/integration/test_phase8_push_delivery.py`: RU recipient, EN recipient, different actor/recipient locales, missing/invalid fallback where supported, both recipients in one batch, special branches, preserved announcement content and locale change before a retry.
9. Use a fake sender/test transport. Do not send real browser notifications to real users to validate this batch.
10. Add completed backend files to scopes, extract, translate and run the targeted tests plus the i18n gate.

**P2 exit:** all Family routes and states inspected, shared dependencies needed by Family translated, generated push text uses the recipient's language, phase gates/evidence complete. Do not claim “Family fully English” while leaving verdict labels or server response strings Russian.

**P2 completion evidence (2026-09-24):** P2.1–P2.3 translated the scoped Family screens and required shared product/content components; authors' content, child/course/group names and compiled worksheet labels remain source data. P2.4 reads `auth_accounts.locale` in the delivery claim and translates recognized generated payload text at retry time, with `ru` fallback. Generated Family/Product/Content/backend catalogs and the exact P2 scopes are in the implementation. Targeted push pytest passed 13 tests; the complete frontend unit suite passed 901 tests; complete pytest passed 124 tests with 1 skip; lint, typecheck, build, frontend/backend catalog checks and three-browser `e2e:i18n` passed (15 tests). The clean `7fbbeb15` comparison records maximum initial-JS growth of 3.2 KB and maximum FCP difference of 20 ms; see [i18n-performance-report.md](../i18n-performance-report.md).

### P3 — Student, submission flows, support and default feedback

**P3.1: Student home, tasks, progress, profile and content controls.**

- Start with `student-home-page.tsx`, `student-home-view.ts`, `student-tasks-page.tsx`, `student-tasks-view.ts`, `student-progress-page.tsx`, `student-profile-page.tsx`, `pages.tsx`.
- Then inspect `student-task-detail-page.tsx`, `student-readable-task-page.tsx`, `student-collapse-action.tsx`, `content-page.tsx`, `student-submission-deadline-notice.tsx` and routes.
- Reuse translated P2 shared labels. Add missing lesson-block controls from `packages/product/src/lesson-blocks.tsx` when they are visible to students.
- Cover offline data, missing lesson, previous/current lesson, loading/failure and hidden material states.

**P3.2: Short-answer and written submissions.**

- Inspect `student-written-submission.tsx`, `student-written-chat.ts`, `image-compression.ts`, worker error propagation and `student-oral-admission.tsx`.
- Shared entry points: `test-answer.tsx`, `submission-composer.tsx`, `answer-validation.ts`, `answer-spec.ts`, `attachment.tsx`, `chat-composer.tsx`, `task-chat.tsx`, `feedback-thread.tsx`, `attempt-timeline.tsx`, `reaction.ts`, `reaction-picker.tsx`, `verdict-panel.tsx`, `oral-admission.tsx`. A filename beginning with `test-` can be production UI: exclude `*.test.tsx`, not every filename containing `test`.
- Preserve answer tokens, validation regexes and API request values. A Russian answer option can be valid lesson data.
- Cover file limits, upload failure, validation, draft recovery, offline queue, retry, submission success, review state and deadline changes.
- Inspect backend `submission_routes.py`, `written_submission_routes.py`, `oral_window_routes.py` and supporting helpers actually producing visible errors.

**P3.3: Default feedback on all response paths.**

- Trace `models/pwa/submissions.py` → `db_methods/pwa/submissions.py` → `apps/pwa_api/submission_routes.py`.
- Inventory built-in feedback, including format errors, pending-checker status, unavailable checking, correct and wrong defaults.
- Implement the safe read-time strategy from §7.5.
- Cover initial submit response, idempotent retry response, attempt history and recheck results. Search Family/Staff views of the same data.
- Test custom feedback, including custom Russian text, custom English text, null values and an ambiguous phrase identical to a default. Do not infer that any Cyrillic feedback is a default.
- Verify the stored record is unchanged when EN reads it.

**P3.4: Student support, organizers, news and notifications.**

- Inspect `student-support-pages.tsx`, `student-photo-support-composer.tsx`, `student-news-page.tsx`, `student-notifications-page.tsx` and all associated routes.
- Shared entry points: `support-dialogue.tsx`, `question-photos.tsx`, `conscious-disclosure.tsx` and previously translated organizer/notification components.
- Inspect backend `support_routes.py` and remaining Student-visible errors.
- Preserve student questions, staff replies, photos' content and news bodies.
- Verify create/reply/failure/empty/offline states in English.

**P3 exit:** every Student route is reviewed, answer and upload behavior is unchanged, default feedback is localized with documented provenance limits, user content remains unchanged, RU/EN submission and support journeys pass.

**P3 completion evidence (2026-09-24):** P3.1–P3.4 translated the declared Student and shared submission/support scopes. Answers, option tokens, regular expressions, IDs, names and authored content remain source data. Test feedback carries a private `built_in` provenance only when it was generated from a null configuration default; it is stored in new idempotency receipts but is never added to the public response schema. The PWA adapter localizes that proven source on initial response, retry and history, while custom text, source-text collisions and history whose immutable revision/evaluation version does not prove the source remain unchanged. Focused feedback pytest passed 3 tests; the full Python suite passed 123 tests with 2 skips; frontend unit passed 902 tests; lint, typecheck, build and frontend/backend catalog checks passed. `e2e:i18n` passed 18 tests across Chromium, WebKit and Firefox; support E2E passed 3 tests. P2 → P3 maximum initial-JS growth was 4.7 KB and maximum cold FCP difference was 4 ms; see [i18n-performance-report.md](../i18n-performance-report.md). Start P4 in the next session.

The current broad Storybook and feature E2E suites still contain separately scoped historical failures: five Storybook files/13 tests lack Storybook auth or activate verdict labels at module load; three submissions offline expectations, three oral current-lesson expectations, and the first scheduled-news scenario do not currently complete. Do not call those suites green without a fresh baseline comparison and focused repair.

### P4 — Staff review, live marking, results and statistics

**P4.1: Review queue and workspace.**

- `review-queue-page.tsx`, `review-queue-model.ts`, `review-workspace-page.tsx`, `review-transfer.tsx`, `review-errors.ts`, `review-draft.ts`.
- Shared `review-queue.tsx`, `review-lock.tsx`, `review-feedback-form.tsx`, `review-verdict-actions.tsx`, `three-pane-review.tsx`, `written-material-reassignment.tsx`, review annotation components.
- Backend `review_routes.py` and written-submission review paths.
- Cover queue filters, assignment, locking/conflict, empty state, save, transfer, permission failures and expired edits.

**P4.2: Review history, series and reactions.**

- `review-history-page.tsx`, `review-history-search.ts`, `review-series-page.tsx`, `review-series-model.ts`, `review-reaction-inbox-page.tsx`, `last-completed-review.ts`.
- Shared `written-review-history.tsx`, `review-reaction-inbox.tsx` and reaction/verdict registries.
- Inspect API `reactionLabel` and other persisted/generated labels. Localize known labels by stable IDs at the boundary; preserve comments and historical unknown content.
- Verify visibility restrictions are unchanged and internal reactions never leak to Student/Family.

**P4.3: Live marking.**

- `live-marking-page.tsx`, `live-marking-grid.tsx`, `live-marking-condition.tsx`, `live-marking-state.ts` and relevant sections of `pages.tsx`.
- Backend `live_marking_routes.py`.
- Translate toolbar/filter labels, row summaries, accessible cell descriptions, conflicts and transfer errors.
- Keep verdict codes and keyboard commands unchanged. Follow §5.8; no per-cell formatter construction.

**P4.4: Student results, oral results and statistics.**

- `student-results-page.tsx`, `student-results-history.tsx`, `staff-oral-results-page.tsx`, `staff-statistics-page.tsx`, `lesson-statistics.tsx`, `statistics-student-search.tsx`, `statistics-recalculation-control.tsx`, `family-digest-panel.tsx`.
- Backend `student_results_routes.py`, `oral_result_routes.py`, `staff_statistics_routes.py`, `statistics_recalculation_routes.py`.
- Include shared `packages/product/src/test-attempt-recheck.tsx` and its progress/result/error states when reviewing test-answer rechecks.
- Translate tables, chart axes/tooltips/accessible labels, filter options, progress/failure states and generated summaries.
- Preserve export contracts and Russian person sorting. Handle any user-facing export headings only after distinguishing them from a fixed machine format.

**P4 exit:** review → verdict → history, live marking and statistics work in both locales; visible server labels are covered; hot-list performance remains within budget.

### P5 — Staff course administration, scheduling, rooms, oral sessions, news

**P5.1: Courses and schedules.**

- `staff-course-catalog-page.tsx`, `course-catalog-editors.tsx`, `course-catalog-draft.ts`, `staff-course-schedule-page.tsx`, `course-schedule-editor.tsx`, `course-schedule-draft.ts`.
- Shared `course-admin.tsx` and `course-context.tsx`.
- Backend `admin_course_routes.py`, `admin_schedule_routes.py`, `course_routes.py`, `admin_enrollment_routes.py` as used by this UI.
- Translate controls, validation and status labels; preserve course/group names/codes and schedule semantics.

**P5.2: Room catalog, layouts, assignment and delivery.**

- `classroom-catalog-page.tsx`, `classroom-layout-page.tsx`, `classroom-event-page.tsx`, `classroom-assignment-page.tsx`.
- Shared `classroom-planning.tsx`, `classroom-delivery.tsx`, `in-person-event.tsx`.
- Backend `classroom_routes.py`, `classroom_layout_routes.py`, `classroom_assignment_routes.py`, `classroom_delivery_routes.py`; inspect `helpers/pwa/classroom_import.py` diagnostics.
- Preserve XLSX compatibility, named rooms, assignment IDs/version logic and Telegram delivery bodies.
- Test draft/stale/confirmed/replaced/conflict states with the current assignment implementation; do not follow superseded historical assumptions.

**P5.3: Oral windows and publishing.**

- `staff-oral-windows-page.tsx`, `oral-weekly-draft.tsx`, `staff-news-page.tsx`, `staff-local-news-composer.tsx`, `local-news-draft.ts`, `staff-group-banners-page.tsx`.
- Shared `oral-result-form.tsx`, `staff-publishing.tsx`, `staff-outreach.tsx`, `news-moderation.tsx`.
- Backend `oral_window_routes.py`, `news_routes.py`, `news_moderation_routes.py`, `group_banner_routes.py`.
- Translate authoring interface, scheduling controls and diagnostics. Preserve post/banner text and rendered publication content.

**P5 exit:** all course/admin surfaces and routes in this phase are covered, including alternate dialogs and errors; schedule/room/import/Telegram behavior remains unchanged.

### P6 — Staff content, lessons, import, synonyms, figure layout and whiteboard

**P6.1: Content editing, review and lessons.**

- `content-page.tsx`, `problem-review-workflow.tsx`, `problem-review-draft.ts`, `staff-lessons-page.tsx`, `staff-lesson-block-editor.tsx`, `staff-worksheet-preview.tsx`, `rich-markdown-editor.tsx`, `lesson-video-dialog.tsx`, `revision-assets-recovery.tsx`.
- Shared content package and `packages/product/src/lesson-blocks.tsx`, metadata-grid UI and `content-update-marker.tsx`.
- Backend `content_routes.py`, `lesson_block_routes.py`, relevant content service diagnostics.
- Translate editing controls and status/error UI. Preserve Markdown, LaTeX, video URLs, author content, generated lesson labels and compiled assets.
- Inspect helper-generated diagnostics shown in successful responses; they are not all `PwaApiError`.

**P6.2: Import, bulk upload and synonyms.**

- `problem-import-page.tsx`, `bulk-content-upload.tsx`, `bulk-content-upload-model.ts`, `problem-synonym-page.tsx`, `automatic-problem-match-plan.ts`.
- Shared `problem-matching.tsx`, `synonym-context.tsx`, metadata-grid validation/clipboard modules.
- Backend `problem_import_routes.py`, `problem_synonym_routes.py` and the helpers they call.
- Keep sheet identifiers such as `Задачи` / `Старые`, TSV/XLSX column names and protocol JSON intact. Translate explanations around those identifiers and visible import diagnostics.
- Verify valid and invalid import previews retain identical parsed values.

**P6.3: Figures and whiteboard export.**

- `figure-layout-editor.tsx`, `whiteboard-export-page.tsx`, `whiteboard-export-generator.tsx`, `whiteboard-zip.worker.ts`.
- Backend `whiteboard_export_routes.py`, relevant `helpers/pwa/content/figure_layout.py` diagnostics.
- Translate controls, progress and errors. Inspect actual output generation: preserve mathematics, source content and documented export formats.
- Do not add React context to a worker. If it returns an application-owned error code, translate the message in the UI consumer.
- Do not translate prompt instructions for a metadata-generation model merely because they are Russian: distinguish internal model instructions from UI diagnostics.

**P6 exit:** content tooling is English while imported/published lesson content and file formats are unchanged; generation/import errors are readable in English; RU regression checks pass.

### P7 — Staff users, access, audit, Telegram bindings, analytics and support

**P7.1: Accounts and student directory.**

- `account-provisioning-page.tsx`, `account-provisioning-batch.ts`, `account-provisioning-tsv.ts`, `student-account-creator.tsx`, `student-account-controls.tsx`, `student-account-draft.ts`, `student-account-batch-panel.tsx`, `student-account-batch-draft.ts`, `student-enrollment-draft.ts`.
- `teacher-batch-panel.tsx`, `teacher-batch-tsv.ts`, `family-account-manager.tsx`, `family-account-draft.ts`, `staff-student-directory-page.tsx`, `student-directory-search.ts`, `users-section-tabs.tsx`.
- Backend `admin_account_routes.py`, `account_batch_routes.py`, `admin_enrollment_routes.py`.
- Translate validation and user controls, not usernames, passwords, names, import headers or copied machine credentials. Inspect generated human instructions separately from fixed credential export formats.

**P7.2: Access, audit and bindings.**

- `staff-access-page.tsx`, `staff-access-draft.ts`, `staff-audit-page.tsx`, `telegram-bindings-page.tsx`.
- Backend `staff_access_routes.py`, `audit_routes.py`, `telegram_binding_routes.py`.
- Localize display names for audit actions while preserving action IDs and historical event data. Translate fallback labels with known semantics; do not translate arbitrary serialized audit payload values.

**P7.3: Overview, analytics and support.**

- `staff-dashboard-page.tsx`, `product-analytics-page.tsx`, `staff-support-pages.tsx`, `staff-support-utils.ts`, remaining sections of `pages.tsx` and all Staff route files.
- Backend `staff_dashboard_routes.py`, `product_analytics_routes.py`, `support_routes.py`, organizer routes not fully covered earlier.
- Cover charts, filters, empty/loading/error states, support actions and generic fallback names.

**P7 exit:** inspect every non-generated Staff route and follow every remaining Cyrillic hit. No Staff page is left unassigned merely because its filename was absent from a batch list. All feature-level production files can now be put under complete frontend scopes, except explicitly scheduled P8 work.

### P8 — Complete coverage, remaining labels, Landing, maintenance and final audit

**P8.1: Landing.**

- Translate `apps/landing/src/landing-page.tsx`, its accessible brand labels, links, descriptions and footer.
- Recheck `main.tsx` and HTML entry metadata. Preserve the install-manifest exclusion.
- Verify cookie-selected English before sign-in and Russian without a preference. Do not create an extra account setting or redesign Landing to add a new control unless explicitly requested.

**P8.2: Remaining persisted/generated labels.**

- Repeat the backend trace for reaction labels, verdict labels, fallback names, audit descriptions, warning lists and any API fields rendered directly.
- Resolve known labels using stable IDs where available. Keep arbitrary historical content intact.
- Close or explicitly escalate the default-feedback provenance limitation from P3. An unresolved required behavior prevents declaring P8 complete.

**P8.3: Maintenance/bootstrap states.**

- Inspect `vmshpwa/deploy/nginx/vmshpwa.conf.template`, the corresponding gateway behavior in `vmshpwa/scripts/e2e_gateway.py`, `packages/contracts/src/service-availability.ts` and `packages/app-shell/src/service-availability.tsx`.
- Implement the already planned **bilingual** static maintenance message where Python/React/catalog loading is unavailable. Keep it short and include both Russian and English.
- Preserve HTTP 503, JSON shape, `service_updating`, retry/cache headers and automatic reconnect behavior.
- Keep test gateway behavior consistent with production configuration.
- Recheck `packages/i18n/src/catalog-failure.ts`: missing catalogs must show a useful bilingual recovery screen, not an ID/hash or a blank page.
- Add focused maintenance/bootstrap assertions; do not introduce a new maintenance architecture.

**P8.4: Broaden guards and prove coverage.**

- Broaden frontend scopes to all production app/package TS/TSX once each area is audited. Include production helpers and worker consumers, not just routes.
- Keep generated files, test fixtures and stories under the intended exclusions. Explain any production-data exception locally with the exact linter rule and a concrete reason.
- Broad backend scope globs alone only cover extractable messages. Audit successful response labels separately and mark application-owned source literals so they are extracted.
- Ensure all nonobsolete frontend English entries and all in-scope backend entries are nonempty; inspect English translations for accidental copied Russian and malformed placeholders.
- Add or strengthen narrowly focused checker tests if necessary: missing translation, unwrapped production UI text, a newly added backend literal, dynamic backend messages, and an unmerged shared catalog must fail the appropriate gate. Do not make a “no Cyrillic anywhere” regex ban that rejects data and source-language macros.
- Run a final raw scan of source and visible English UI. Explain each retained Russian item as source text, data/content, technical syntax, developer text or the explicitly bilingual fallback.

**P8.5: Final English and Russian walkthrough.**

Use the real isolated API runner, not MSW in E2E. Check Student, Family, Staff and Landing. Exercise primary journeys and secondary dialogs, not just initial headings. Run the full gates and final performance report. Fill P2–P8 completion evidence in `24-i18n.md` and both status files.

## 9. Tests and quality gates

### 9.1 Per-batch checks

1. Review `git diff` before running broad commands.
2. Format only changed files during iteration. `make pwa-format` runs `prettier --write .` across the workspace, so do not use it casually on unrelated work.
3. Extract catalogs and fill translations.
4. Run targeted component/helper tests and targeted lint for changed files.
5. Run targeted backend tests if messages, serialization, push or stored-label behavior changed.
6. Run `make pwa-i18n-check`.
7. Inspect at least the affected English visual states; record route/story and result.
8. Review the final diff for accidental data/protocol modifications and unnecessary lockfile changes.

### 9.2 React tests

Components needing Lingui/locale context use:

```tsx
import { renderWithI18n } from '@vmsh/test-utils/i18n'

renderWithI18n(<ComponentUnderTest />)
```

The existing helper composes a supplied wrapper, so preserve router/query providers. Do not delete providers just to add i18n. `dev/test-support/i18n-setup.ts` activates Russian, preloads English and resets to Russian after tests.

For English, use the existing `activateLocale('en', loaders)` setup with real compiled catalog loaders, following nearby i18n tests; do not activate an empty English catalog and assert fallback text. If using the workspace-wide loader, calculate the correct relative path to `dev/test-support/i18n-catalogs.ts` for that test. Do not add a production dependency on test utilities.

Select meaningful cases:

- static and interpolated messages;
- zero/one/many counts and number/date output;
- status/registry labels after locale activation;
- an error and empty state;
- accessible names;
- user data remaining unchanged;
- a value sent to an API staying identical between locales.

Do not write a test for every translated word or replace all Russian assertions with English. Keep the existing Russian regression suite and add representative English behavior checks.

### 9.3 Backend tests

Use existing `pwa_tests` fixtures and isolation. Starting points:

- `pwa_tests/test_pwa_i18n.py`;
- `pwa_tests/integration/test_auth_http_api.py` for cookie/account behavior examples;
- `pwa_tests/integration/test_phase8_push_delivery.py`;
- `pwa_tests/domain/test_pwa_test_submissions.py`;
- relevant submission/review/content HTTP integration tests found with `rg --files pwa_tests`.

Assert language-dependent messages **and** unchanged status/code/data. For interpolation, check the same parameters in RU and EN. For data read-time translation, assert storage does not change. For push, actor and recipient languages must be deliberately different in at least one test.

### 9.4 English E2E

Extend [e2e/i18n.spec.ts](../../e2e/i18n.spec.ts), using its existing fixtures and login helpers. Tests that change the account language must restore Russian in `finally`, as the existing tests do. A cookie set before login may be replaced by the account's saved preference; use the actual account language flow for authenticated English tests.

| Phase | Required representative English journey                                                               |
| ----- | ----------------------------------------------------------------------------------------------------- |
| P2    | Family home → child/progress → notifications/settings; organizer form; push payload tested in backend |
| P3    | Student task → validation/submit → feedback/history; written upload/retry; support                    |
| P4    | Staff queue → review → verdict/history; live marking; statistics                                      |
| P5    | Course/schedule form → validation; room assignment; oral window; news editor                          |
| P6    | Content editor → validation; import preview; figure/whiteboard controls                               |
| P7    | User search/provisioning validation; access/audit; dashboard/support                                  |
| P8    | Landing before login; maintenance/catalog failure; final audience walkthrough                         |

A single E2E need not exercise every listed state. Cover the matrix with a combination of focused tests and documented visual inspection. Do not assert that the entire page contains no Cyrillic: legitimate user/course/lesson data is Russian. Assert specific application-owned controls and inspect unexpected Russian strings by origin.

### 9.5 Storybook and visual review

Use the existing global “Язык интерфейса” → English. Review affected stories, including empty/error/disabled/dialog states, at narrow and wide widths. Check truncation, wrapping, button widths, table headers, tooltips and screen-reader labels. Preserve both themes and applicable browser checks. Do not update snapshots without inspecting the rendered difference.

If a Storybook interaction has Russian text selectors, keep its normal Russian test valid. For an interaction intended to execute under both globals, make its expectations explicitly locale-aware or use a stable semantic selector that still proves the behavior. Do not remove assertions to avoid an English failure.

### 9.6 Phase completion commands

From repository root, after selecting the supported pnpm:

```sh
make pwa-i18n-extract
make pwa-i18n-check
make pwa-lint
make pwa-typecheck
make pwa-test
make pwa-build
make pwa-storybook-test
make pwa-e2e-i18n
```

Also run the relevant feature E2E target(s) present in the Makefile: `pwa-e2e-family`, `pwa-e2e-submissions`, `pwa-e2e-review`, `pwa-e2e-support`, `pwa-e2e-classrooms`, `pwa-e2e-oral`, `pwa-e2e-news`, `pwa-e2e-content`, as applicable. Do not invent a Make target from a pnpm script name; check the actual Makefile first.

`make pwa-test` runs frontend unit tests and the PWA Python suite. Use `make pwa-e2e-auth` and `make pwa-e2e-runtime` if the batch affects startup, auth, shared catalog loading or isolation. P8 requires `make pwa-e2e` as the final broad regression run.

For repository-wide formatting verification, use `cd vmshpwa && pnpm format:check`. If the project gate requires `make pwa-format`, inspect resulting changes and preserve unrelated work; do not sweep unrelated formatting into the translation change.

Record command, revision, outcome and known limitations. A historical failure is not automatically a current baseline failure. Do not hide a new failure by listing it under an old generic warning.

## 10. Performance checks after each completed phase

After building, run from `vmshpwa/`:

```sh
node scripts/bundle-report.mjs
node scripts/startup-benchmark.mjs --runs 9 student family staff landing
```

Passing explicit app names matters: the startup script's default list excludes Landing. The benchmark uses a short-lived local server on an ephemeral loopback port; it does not need the human development server or production API.

Compare with [i18n-performance-report.md](../i18n-performance-report.md), keeping the existing P0/pre-i18n reference and recording the immediately preceding phase too:

- Initial JS, entry plus modulepreload, Brotli: maximum +10 KB per app against the plan's baseline.
- Cold and warm median FCP: maximum +30 ms.
- Build and frontend test duration: maximum +25%.
- Catalog request starts in parallel with startup, not as a new sequential waterfall.
- Student/Family service workers retain both language catalogs in precache.
- High-volume review/marking/directory rendering has no new per-cell formatter construction.

Record machine/tool versions and measurement method. The original timings are from a much earlier revision, so unrelated product growth must be reported separately with an appropriate comparison; do not silently reset the accepted budget. If a budget is exceeded, investigate and document the delta. Do not “pass” it by omitting a catalog from the size calculation or changing the baseline without an explicit decision.

## 11. Scope-gate rules and false confidence to avoid

Add exact completed file globs first. Use a directory glob only when every production file in that directory has been inspected. Frontend paths are relative to `vmshpwa/`; backend paths are relative to the repository root.

Example shape, not a command to append these immediately:

```json
{
  "frontend": ["apps/family/src/**/*.{ts,tsx}"],
  "backend": ["apps/pwa_api/family_course_routes.py"]
}
```

Preserve existing entries when adding new ones.

A green gate does **not** prove:

- an unmarked UI string has been extracted outside declared frontend scopes;
- every successful backend response label is marked;
- an English translation is semantically correct;
- all placeholders survive in the correct role;
- custom content has not been translated by mistake;
- a cold-loaded registry is in the correct language;
- maintenance outside Python is English;
- all frontend source files are synchronized if `--no-extract` was used;
- the English layout fits on a phone.

These require inventory review, focused tests and visual inspection.

For legitimate data hits, use the smallest applicable `lingui/no-unlocalized-strings` suppression with a specific reason, following existing code. Do not add file-wide disables to large feature pages. Do not remove the Cyrillic detector, loosen it to ignore whole phrases or move user-visible strings to unscanned files.

## 12. Troubleshooting and when to ask the owner

| Symptom                                | First action                                                                | Do not do                                        |
| -------------------------------------- | --------------------------------------------------------------------------- | ------------------------------------------------ |
| UI shows a hash/message ID             | Check extraction, catalog ownership and both merge files                    | Add the hash as display text                     |
| English page shows Russian UI          | Check marker, `msgstr`, loaded catalog, producer and current account locale | Assume every Russian string is lesson content    |
| Lint rejects module `t`                | Move evaluation into a function or use `msg` descriptors                    | Disable `t-call-in-function`                     |
| Tests cannot find Lingui context       | Use `renderWithI18n` while preserving existing providers                    | Mock away all translated components              |
| Placeholder error or braces on screen  | Compare extracted message variables and PO syntax                           | Delete the variable                              |
| Catalog synchronization fails          | Extract, inspect diff, translate new messages and rerun                     | Skip extraction forever                          |
| Push remains Russian                   | Check recipient locale in claimed DB row and every payload branch           | Read a request cookie inside the delivery worker |
| Some registry labels stay Russian      | Find eager module arrays/spreads and resolve at use time                    | Add a second arbitrary locale-switch listener    |
| A protocol/import test changes         | Restore raw values; translate presentation only                             | Update fixtures to match a broken format         |
| A new dependency/lockfile diff appears | Check pnpm version and why the dependency is needed                         | Accept package-manager churn                     |

Proceed without asking for approval for ordinary local translation edits and checks within these requirements. Ask a specific question only when implementation encounters a real unresolved product decision, for example:

- Historical default feedback cannot be distinguished safely from custom authored text.
- A new domain term has two materially different meanings not resolved by the glossary or source behavior.
- Required performance cannot be met without changing the accepted architecture or budget.
- A requested behavior would change a preserved import/export format or Telegram output.

When asking, include the exact file/field, observed ambiguity, recommended option and consequences. Continue independent translation work while waiting. Do not ask again about Russian source text, US English, brand spelling, default locale or the already accepted exclusions.

## 13. Completion checklist and handoff format

A phase is verified only when all applicable items are true:

- [ ] All listed/discovered routes, components and response fields have an inventory disposition.
- [ ] Every application-owned phrase in that area is extractable and translated.
- [ ] Catalog ownership and app merges are correct.
- [ ] English grammar, vocabulary, placeholders, plurals and date/number formatting are reviewed.
- [ ] User/course/lesson content and machine values are unchanged.
- [ ] Source Russian behavior remains intact.
- [ ] Completed file scopes are added without hiding unfinished files.
- [ ] Targeted tests and required phase gates pass, or an actual blocker is explicitly recorded and the phase remains incomplete.
- [ ] English visual review covers the relevant states and widths.
- [ ] Performance results are recorded against the accepted budget.
- [ ] `24-i18n.md`, both status files and the performance report are updated as applicable.
- [ ] No credentials, production data, generated build directories or unrelated edits are included.

Final implementation report:

```text
Completed phase/batches:
Files and UI areas changed:
Catalogs and scopes updated:
Preserved data/protocol boundaries:
Tests and exact results:
English visual evidence:
Performance measurements:
Remaining gaps/blockers, with exact files:
Next executable batch:
```

For the next execution session, start with the P3 preparation and P3.1. Do not restart completed P0–P2 and do not jump to a repository-wide replacement of Russian strings.
