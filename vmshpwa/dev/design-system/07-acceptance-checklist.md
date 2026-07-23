# Итоговый acceptance checklist

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
- [ ] До 10 фото: worker progress, delete/re-upload ordering, preview, retry, offline queue.
- [ ] Immutable evidence и annotation overlay разделены.
- [ ] Feedback/resubmission history не теряется.
- [ ] Telegram-rich news, albums, math и два preview готовы.
- [ ] Offline/reconnect/update/push states недвусмысленны.
- [ ] Dense tables, TSV, bulk actions, locks, diagnostics и missing assets готовы.
- [ ] Classroom planner не тянет DnD dependency; pointer/native перенос имеет простой select/move fallback.
- [ ] Progress не содержит рейтингов и цвет-only charts.

## Pages

- [ ] Все Student routes и нижняя навигация реализованы.
- [ ] Все Family routes, child context и self-check реализованы.
- [ ] Все Staff routes и capability states реализованы.
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
- [ ] Документация и `STATUS.md` соответствуют фактическому решению.

## Финальная ручная проверка

Владелец продукта должен без подсказки выполнить на телефоне: найти текущую задачу, прочесть длинное условие, подготовить offline-письменную сдачу, понять её sync state и открыть feedback. На desktop преподаватель должен найти очередь, захватить работу, разметить фото, отправить verdict и перейти дальше. Любая неоднозначность статуса блокирует приёмку.
