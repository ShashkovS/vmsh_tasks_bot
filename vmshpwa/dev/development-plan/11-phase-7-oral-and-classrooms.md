# Этап 7. Устный онлайн-контур, режим присутствия и аудитории

## Результат

Онлайн-школьник видит несколько устных окон, раскрывает Zoom details по tap и при желании отправляет устную задачу в обычную письменную очередь. Staff администрирует устные результаты. Admin распределяет очных учеников и может полностью пересчитать ошибочный план; печать и быстрый очный ввод плюсов относятся ко второй версии.

## Граница v1

- Позиции школьника в устной очереди нет.
- Очный школьник не сдаёт через Student PWA; web-интерфейс учителя в аудитории отложен.
- Аудитория — отдельная от group/level сущность на конкретный lesson/date.
- Teacher не имеет classrooms route; server возвращает `403`.
- Oral task и written-before-oral используют существующие numeric problem types без изменения Telegram semantics.

## Модель данных

Migration: `pwa_oral_windows_classrooms`.

- `oral_windows` с несколькими sequence numbers (текущий процесс использует три), adapter/view над `zoom_conversation`, `zoom_events`, `zoom_queue`.
- `classroom_rooms`, `classroom_assignments`.
- `group_banners` может создаваться здесь или в этапе 8, но oral-window card остаётся отдельным типом UI.
- `user_changes_log` фиксирует online/in-person; audit сохраняет admin assignments/results imports.

## Backend/Staff

- Oral window config создаёт только admin; provider v1 — Zoom, written fallback всегда видим.
- Join details detail endpoint with auth/group/mode checks and no caching/logging secret.
- Staff oral workflow строится через adapter к существующим zoom/result domain functions; не создаёт второй ledger verdict.
- Classroom auto-assignment сначала сохраняет прошлую аудиторию школьника того же уровня, затем максимально равномерно распределяет остальных.
- Manual move uses version check; no DnD library required — select/move actions are sufficient. Visual drag may be local later.
- Print command/list-on-door/conduit package проектируется во второй версии по `a11`–`a14` и не блокирует v1.

## Frontend

- Student oral card: current status, open/close time, join reveal, written composer, offline limitations.
- Mode switch explanation: reserved room/printed materials/teachers and request to switch off in-person when absent.
- Staff `oral.tsx`, `classrooms.tsx`, weekly dashboard counts.
- Classroom planner: capacity, unassigned/conflicts, auto-plan preview, manual move, confirmation and explicit full recalculation. Export/print commands are phase two.

## Tests

- Moscow timezone/DST-independent schedule boundaries and server/client clock.
- Student group/mode authorization for join details; secret excluded from caches/Sentry/WS.
- Mapping oral results to `results`, duplicate import, legacy Zoom history.
- Assignment property tests: no duplicate student, capacities, constraints, stable rerun.
- Characterization of classroom assignment inputs/outputs against `a11` samples; generation of door lists, conduits and PDF packages remains a separate phase-two task.
- Storybook oral states and classroom empty/conflict/full/recalculation/error.
- Playwright online oral written fallback, admin assignment/recalculation, Student/Family room visibility и teacher forbidden.

## Критерии приёмки

- Join secret доступен только eligible online student after explicit tap.
- Oral verdict остаётся совместимым с исторической статистикой/results.
- In-person student отсутствует в online submission CTA, но может безопасно сменить mode после подтверждения.
- Auto-assignment всегда объясняет unassigned/conflicts и не затирает manual plan без confirmation.
- Assignment revision is reproducible and can be recalculated after confirmation; the first version does not expose print commands.

## Пруфы завершения этапа

- [ ] Revision/migration/adapters: `<sha/paths/results>`.
- [ ] Demo online oral + written fallback + Staff result: `<routes/evidence>`.
- [ ] Classroom auto/manual assignment invariant report: `<path/result>`.
- [ ] Join secret authorization/no-log/no-cache tests: `<result>`.
- [ ] Classroom assignment parity evidence against `a11` fixtures; deferred print scope recorded: `<paths>`.
- [ ] Storybook oral/classroom stories/a11y/visual approval: `<ids/paths>`.
- [ ] Playwright 3 browsers + Teacher forbidden: `<result>`.
- [ ] Telegram/Zoom historical tests: `<result>`.
- [ ] Docs/operational runbook/known limitations/acceptance: `<paths/issues/name/date>`.
