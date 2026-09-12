# Phase 7C — распределение школьников по аудиториям

Дата актуальной проверки: 2026-07-29.

## Проверяемый результат

Для выбранного очного события admin получает preview всех активных очных
школьников участвующих групп, пересчитывает и правит draft, подтверждает полный
план и читает неизменяемую историю прежних подтверждённых назначений.

Распределение сначала сохраняет прежнюю допустимую аудиторию той же группы,
затем использует наименее заполненную комнату с natural-sort tie-break. Без
доступной комнаты школьник остаётся `reassigning`, и подтверждение невозможно.
Комната другой группы того же курса требует явного подтверждения смены группы;
комната другого курса запрещена.

Staff хранит незавершённые select/bulk-правки в event/account/version-scoped
`localStorage`. Сервер получает один batch, а не mutation после каждого select.
В строке доступны возраст, класс, автоматически вычисленная сила и история;
заголовки комнат показывают независимые средние значения без подстановки
отсутствующих данных.

## Реализация

- migration: `0059.pwa_classroom_assignments`;
- SQLite operations: `db_methods/pwa/classroom_assignments.py`;
- domain: `helpers/pwa/classroom_assignment.py`,
  `models/pwa/classroom_assignments.py`;
- HTTP: `apps/pwa_api/classroom_assignment_routes.py`;
- contracts/client: `packages/contracts/src/classrooms.ts`,
  `packages/app-shell/src/classroom-client.ts`;
- Staff: `apps/staff/src/features/classrooms/classroom-admin.tsx`;
- production-browser proof: `e2e/classrooms.spec.ts`.

## Зафиксированные инкременты

- `9aa3e20` — schema и базовые операции плана;
- `4bcfbbc`, `91d48e5` — распределение и HTTP boundary;
- `c14e9a4`, `7fafbf1`, `4ad82b1` — contracts, Staff planner и browser path;
- `a54470b` — classroom workflow tests;
- `95c178c`, `55498aa` — подтверждённая смена группы;
- `31e83e3`, `19446bd` — history API/UI;
- `486474a`, `70ad902` — stale/reassigning после смены layout/archive;
- `e0246e1` — одноразовый Excel dry-run/import.

## Проверки

- unit/domain/migration/API проверки распределения, group-change, history и
  stale/archive: **PASS**;
- production-build classroom E2E: **9 PASS** в Chromium, WebKit и Firefox;
- полный frontend unit suite: **439 PASS**;
- полный Python PWA suite после Excel-import: **1324 PASS, 3 SKIP**;
- ESLint/Stylelint, TypeScript и production builds трёх apps: **PASS**;
- snapshots не обновлялись.

## Открытые границы

- Production-size anonymized rehearsal и реальный owner-reviewed Excel preview
  ещё не выполнены.
- Student/Family projection и явная PWA/Telegram-рассылка относятся к
  следующему срезу Phase 7.
- Устные окна и Staff oral workflow ещё не реализованы.
