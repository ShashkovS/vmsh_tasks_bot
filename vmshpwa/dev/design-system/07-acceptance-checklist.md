# Итоговый acceptance checklist

## Состояние автоматической приёмки 25 июля 2026

Phase 5/6 implementation trace находится в [`05-pages-and-flows.md`](05-pages-and-flows.md) и [`06-storybook-and-testing.md`](06-storybook-and-testing.md). Точные page entry points: [`Student`](../../apps/student/src/pages.tsx), [`Family`](../../apps/family/src/pages.tsx), [`Staff`](../../apps/staff/src/pages.tsx); Storybook proof: [`Student stories`](../../apps/student/src/pages.stories.tsx), [`Family stories`](../../apps/family/src/pages.stories.tsx), [`Staff stories`](../../apps/staff/src/pages.stories.tsx), [`classroom matrices`](../../packages/product/src/classroom-planning.stories.tsx).

Автоматический Storybook gate: **121/121**, axe работает в режиме error. Ручной просмотр ключевых page stories, компактного review flow и открытого publication scheduler выполнен на изолированном agent runtime; дефект ориентации Tabs исправлен, внутренние реакции проверены сочетаниями `⌘/Ctrl + Alt + 1–4`, а поле даты — на широком и узком Staff viewport без overlap. Полный gate 25 июля: format, lint, strict TypeScript и production build — green; Vitest **21/21**; Python PWA tests **11/11**; Playwright production-preview E2E/visual **36/36** в Chromium, WebKit и Firefox. После просмотра ожидаемых изменений обновлены и повторно проверены версионируемые baseline из [`e2e/__screenshots__`](../../e2e/__screenshots__). Чекбоксы не считаются принятыми самим автором реализации: финальная визуальная и продуктовая приёмка остаётся за владельцем.

## Brand и art direction

- [ ] Направление явно принято и записано в `STATUS.md`.
- [ ] Новый wordmark «ВМШ 179» и знак 179 различимы в требуемых размерах.
- [ ] Student/Family/Staff icons согласованы и не смешиваются.
- [ ] Есть monochrome, favicon, maskable, light/dark assets и правила использования.
- [ ] Нет маркетинговой, игровой или чрезмерно декоративной эстетики.

## Tokens

- [ ] Primitive → semantic → component layers документированы.
- [ ] Product JSX не содержит raw colors.
- [ ] Светлая/тёмная palettes и contrast pairs приняты.
- [ ] Уровень визуально независим от success/warning/error.
- [ ] Verdict scale визуально независима от уровня; binary/ternary/full registries работают без hardcode.
- [ ] Human и AI provenance невозможно перепутать визуально или семантически.
- [ ] Typography, math, spacing, radius, elevation, z-index, motion заданы tokens.
- [ ] Student touch и Staff compact density проверены.
- [ ] Reduced motion и forced colors имеют рабочую стратегию.

## Primitives

- [ ] Весь обязательный primitive set реализован на Base UI/shadcn foundation.
- [ ] Focus, keyboard, disabled, invalid, loading, long content и dark states проверены.
- [ ] Form label/hint/error связи доступны screen reader.
- [ ] Overlay focus trap/restore и scroll/collision работают.
- [ ] Shared component change включает stories и interaction state.

## Product components

- [ ] Длинный математический документ, formulas, subparts, tables и TikZ/SVG читаемы.
- [ ] Figures доступны и масштабируются keyboard/pointer.
- [ ] Все исторические answer types представлены contract-driven input.
- [ ] Форматная подсветка совпадает с `strip()+fullmatch` legacy, но не ругается на partial input до blur/submit; tuple не показывает «Отправится», list preview появляется только после parsing, weekday использует семь кнопок, `SELECT_ONE` отправляет видимый текст. Реализация: [`TestAnswer`](../../packages/product/src/test-answer.tsx), [`Product/Test answer`](../../packages/product/src/test-answer.stories.tsx).
- [ ] До 10 фото: worker progress, up/down reordering, preview, retry, offline queue.
- [ ] Отдельная «квитанция» сдачи отсутствует; успешная фиксация показана обычным thread/sync status.
- [ ] До первого review lock исходную entry можно изменить/удалить; досланное после lock входит в текущую проверку, а evidence становится immutable только при завершении verdict.
- [ ] Immutable evidence и annotation overlay разделены; overlay поддерживает карандаш, ластик, поворот, zoom и 4–5 цветов и не редактируется после отправки.
- [ ] Feedback/resubmission history не теряется.
- [ ] Последний verdict, раскрываемая история, correction/recheck и частичные веса представлены корректно.
- [ ] Четыре технических task types покрыты; гибрид школьнику выглядит oral и поддерживает written+Zoom window.
- [ ] Hidden Student/teacher reactions проверены permission fixtures и не утекают другой роли; на verdict разрешена одна реакция каждого типа с часовым окном изменения/удаления.
- [ ] Hint и solution скрыты до публикации и требуют осознанного подтверждения.
- [ ] Telegram-rich news, albums, math и два preview готовы.
- [ ] Полное условие задачи показано текстом Telegram Rich Message с headings/lists/math, а не скриншотом.
- [ ] Offline/reconnect/update/push states недвусмысленны.
- [ ] Каждый значимый Student/Staff composer/editor восстанавливает compatible local draft после reload/update, изолирует аккаунты и очищается только после receipt/confirm или explicit discard.
- [ ] Dense tables, TSV, bulk actions, locks, diagnostics и missing assets готовы.
- [ ] Metadata grid имеет task type и copy/paste-compatible dropdown answer type; condition/hint/solution публикуются и планируются независимо.
- [ ] Открытый `datetime-local` публикации остаётся внутри компактной artifact-колонки; кнопки расписания находятся отдельной строкой, соседние condition/hint/solution controls не перекрываются на desktop и narrow Staff viewport.
- [ ] Review list/fast flows, 30-minute lock, occupied/lost-lock, registry verdict shortcuts, compact internal-reaction Mod+Alt shortcuts, comment guard и abandon готовы.
- [ ] Review workspace показывает evidence, существующую переписку и новый teacher reply в одном хронологическом порядке; teacher reactions сохраняют компактный видимый текст.
- [ ] Questions отделены от verdict flow при сохранении migration state Telegram adapter.
- [ ] AI future states покрыты без включения реальной AI-интеграции в первую версию.
- [ ] Classroom catalog поддерживает trim/NFKC/casefold duplicate, rename, active/hidden, archive/restore и optimistic conflict без hard delete.
- [ ] Classroom layout показывает inherited/materialized state, назначает комнате максимум одну группу, использует group marker/tint, выводит `очно/распределено` и не вводит capacity/weights.
- [ ] Classroom student plan сохраняет прежнюю допустимую комнату, затем выбирает least-loaded с natural-name tie-break; single/bulk select, cross-group confirmation, recalculate/confirm работают без drag interaction.
- [ ] Compact flex-wrap planner остаётся обозримым при 6–15 комнатах и примерно 200 школьниках; сортировка всегда по фамилии/имени, неназначенные вынесены отдельно.
- [ ] Age/grade/strength nullable states, room count и отдельные averages возраста/класса/силы, fuzzy search+jump и confirmed classroom history представлены и не раскрывают дату рождения.
- [ ] Local classroom draft переживает reload/update, не теряется при conflict и удаляется только после receipt/confirm либо explicit discard.
- [ ] Stale, reassigning, empty group, no-room incident, фактические 6/5/2 комнаты и historical immutability представлены отдельными stories.
- [ ] Student/Family показывают `not_applicable|reassigning|assigned`; Student notification states есть, Family classroom push отсутствует.
- [ ] Progress не содержит рейтингов, цвет-only charts или маркера/словесного сравнения конкретного школьника с группой.

## Pages

- [ ] Все Student routes и нижняя навигация реализованы.
- [ ] Все Family routes и child context реализованы: полный student-visible thread/evidence, смена level/mode, самостоятельное раскрытие hint/solution и недельные уведомления; self-check отсутствует.
- [ ] Все Staff routes и capability states реализованы.
- [ ] `/staff/classrooms` имеет вкладки «Каталог», «По группам», «Школьники», URL-state `lesson/tab/roomStatus`; Teacher получает forbidden.
- [ ] Staff review работоспособен на телефоне, но не обещает offline verdict/outbox.
- [ ] Login не раскрывает protected content и не создаёт production mock bypass.
- [ ] Search params shareable и runtime-validated.
- [ ] Loading/empty/error/offline/locked/permission states есть на ключевых страницах.
- [ ] Responsive viewports из фазы 5 проверены без потери функций.

## Quality gates

- [ ] Prettier, ESLint, strict TypeScript, Vitest проходят.
- [ ] Storybook build и addon-vitest browser mode проходят.
- [ ] Storybook a11y violations имеют `error`, актуальных violations нет.
- [ ] Staff stories проходят тот же semantic/keyboard/focus/a11y baseline без глобального исключения.
- [ ] Production build не включает MSW/prototype mode.
- [ ] Student/Family injectManifest workers и manifests валидны.
- [ ] Playwright E2E/visual проходят в Chromium, WebKit, Firefox.
- [ ] Visual diffs просмотрены, baseline не обновлён вслепую.
- [ ] Telegram/Google не вызываются новыми unit/E2E.
- [ ] Первый content gate сравнивает три реальных листка одного уровня в PWA, Telegram и PDF; перед выпуском пройдены реальные Android-устройства, iPhone — по возможности.
- [ ] Classroom E2E в трёх браузерах проверяет Unicode duplicate, layout/plan confirm, Student/Family state, archive→reassigning и reassignment на настоящем aiohttp/SQLite.
- [ ] Документация и `STATUS.md` соответствуют фактическому решению.

## Финальная ручная проверка

Владелец продукта должен без подсказки выполнить на телефоне: найти текущую задачу, прочесть длинное условие, подготовить offline-письменную сдачу, понять её sync state и открыть feedback. На desktop преподаватель должен найти очередь, захватить работу, разметить фото, отправить verdict и перейти дальше. Любая неоднозначность статуса блокирует приёмку.
