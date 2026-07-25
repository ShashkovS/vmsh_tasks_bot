# Этап 9. Family PWA, личный прогресс и достижения

## Результат

Родитель переключается между связанными детьми, видит всю student-visible работу и может менять уровень/режим ребёнка. Отдельного self-check нет. Student видит accepted counts, распределение решённых задач, календарь и достижения; Family не получает сравнение с группой.

## Модель данных/read models

Migration: `pwa_family_achievements`.

- `family_student_links` создана в фазе 1 и batch-filled здесь production-данными.
- `achievement_definitions`, `user_achievements`; self-check table/API не создаются.
- Stats сначала derived из `results`, `test_attempts`, `submission_entries`, reviews и mode/group history.
- Текущий level/mode интерпретируется на момент события через `user_changes_log`; смена уровня не переписывает историю.
- Violin показывает число решённых problem items, скрыт до `publishedAt + 7 days` и при sample size меньше 30; cohort прошлого урока выбирается по лучшему результату школьника среди уровней.
- Numeric verdict weights нужны расчёту, но student headline остаётся «3 задачи зачтено…», без leaderboard/position.

## Family permissions

- Family child ID всегда проверяется через link.
- Family видит фотографии, thread, comments, annotations, history verdicts, student-visible AI и реакцию ребёнка; скрытая teacher reaction исключается server serializer.
- Family может менять active group и attendance mode ребёнка, но не отправляет решение от его имени.
- Минимальный read-only экран актуальной аудитории и `not_applicable|reassigning|assigned`, созданный в этапе 7, сохраняется при сборке полного Family home. Classroom push не добавляется.
- Child switcher не смешивает TanStack Query/Dexie cache между детьми.

## Progress UX

- Summary counts: accepted/partial/needs work/submitted/unreviewed per chosen interval.
- One progression chart over all lessons using `visx` + `d3-array/scale/shape`.
- Violin per lesson after grace; accessible textual summary/table exists alongside SVG.
- GitHub-style activity calendar считает один active event на problem item в день независимо от числа посылок.
- Streak хранит число недель подряд с 1+, 2+, 3+ и 4+ активными днями.
- Achievements: первая отправка, первая письменная, первое завершённое занятие, занятие с результатом не ниже максимума и streak milestones; выполняется historical backfill.
- Empty/new-student/level-change/late-data/correction states explicit.

## Routes/files

- Existing Family routes: `children.*`, `tasks.$taskId`, `news.*`, `profile.*`.
- Student `progress.tsx`.
- Features: `family/src/features/children|progress|profile`; `student/src/features/progress`.
- Shared chart logic may live in a new product package only if reuse is real; raw charts do not enter `packages/ui`.

## Tests

- Permission matrix: multi-child, revoked link, guessed ID, two parents if supported.
- Historical group/mode reconstruction and corrections in results.
- Weight/counter/grace/cohort/privacy/activity calendar property tests.
- Chart domain/empty/single point/extreme/outlier/1500 students performance; SVG a11y summary.
- Family multi-child feed дедуплицирует общие новости и подписывает child/group-specific entries; first-version history UI ограничен текущим сезоном.
- Achievement rule version/backfill/duplicate/no-ranking tests.
- Storybook Family mobile-light then desktop/dark; progress charts at all states.
- Playwright child switch/cache isolation/group-mode change/progress grace and Student progress.

## Критерии приёмки

- Family не может открыть несвязанного ребёнка или сдать его работу, но может менять его level/mode.
- Переключение детей меняет весь scoped state без flash чужих данных.
- Group distribution появляется только после grace и `n >= 30`; Family его не видит.
- Исправленный/новый result детерминированно пересчитывает read model.
- Графики понятны без цвета/hover и не создают рейтинг.
- Achievement rerun не выдаёт дубликаты.

## Пруфы завершения этапа

- [ ] Revision/migration/family link import dry-run: `<sha/paths/results>`.
- [ ] Demo multi-child/full thread/group-mode change/Student progress: `<routes/evidence>`.
- [ ] Permission/cache isolation tests: `<result>`.
- [ ] Statistics formulas, SQL plans and golden expected values: `<path/result>`.
- [ ] Grace/privacy/1500-student performance evidence: `<path/result>`.
- [ ] Storybook charts/family pages/interactions/a11y/visual approval: `<ids/paths>`.
- [ ] Playwright 3 browsers: `<result>`.
- [ ] Achievement definitions/rule version proof: `<path/result>`.
- [ ] Docs/data definitions/known limitations/acceptance: `<paths/issues/name/date>`.
