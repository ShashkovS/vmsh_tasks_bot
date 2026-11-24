# Phase 10 — Staff UI семейных аккаунтов

Дата проверки: 2026-08-02.

## Проверяемый результат

Admin в каталоге школьников может:

- создать отдельный Family-аккаунт и сразу связать его со школьником;
- связать со школьником существующий Family-аккаунт по логину;
- видеть имя, логин, роль и признак основного семейного контакта;
- отозвать только связь с выбранным школьником, не удаляя аккаунт и другие связи;
- отдельно блокировать аккаунт и менять его пароль существующим lifecycle-контролом.

Несекретные поля незавершённой формы переживают reload в scope
`runtime + Staff account + Student + action`. Пароль существует только в
React-state, отсутствует в draft schema, очищается после успешного ответа и не
возвращается API.

## Реализация

- Zod contracts и fixture:
  `vmshpwa/packages/contracts/src/admin-student-enrollments.ts`,
  `vmshpwa/packages/contracts/fixtures/admin-enrollments/directory.v1.json`;
- HTTP client: `vmshpwa/packages/app-shell/src/admin-course-client.ts`;
- draft boundary: `vmshpwa/apps/staff/src/family-account-draft.ts`;
- Staff UI: `vmshpwa/apps/staff/src/family-account-manager.tsx` и
  `vmshpwa/apps/staff/src/staff-student-directory-page.tsx`;
- Storybook: `Pages/Staff--family-account-management`;
- production browser flow: `vmshpwa/e2e/authentication.spec.ts`, сценарий
  `Admin creates a Family login without persisting its password in the browser`.

Backend/API proof находится отдельно в
`pwa_tests/reports/phase10-family-account-backend.md`.

## Проверки

- targeted Vitest: 3 файла, 17 тестов — PASS;
- ESLint + Stylelint — PASS;
- strict TypeScript + route generation — PASS;
- полный unit regression: 103 файла, 570 тестов — PASS;
- полный Python PWA regression: 1504 passed, 5 skipped — PASS;
- Storybook browser mode: 47 файлов, 227 tests — PASS;
- production-build authentication E2E: 79 passed, 8 ожидаемо skipped — PASS;
- новый браузерный create/reload/login flow — PASS в Chromium; общие read-only
  authentication paths остаются проверены Chromium, WebKit и Firefox;
- ручной осмотр `Pages/Staff--family-account-management`: desktop 1280 px и
  mobile 390 px, light theme — принято; горизонтального переполнения формы нет;
- visual snapshots не обновлялись.

Первый sandboxed запуск Python-набора был недействителен: окружение запрещало
временные loopback bind и ImageMagick. Тот же неизменённый набор повторён с
разрешёнными локальными сокетами/бинарниками и полностью прошёл.

## Осталось в Phase 10

Этот инкремент не закрывает создание Student-аккаунта, полный users import,
metadata grid, Google cutover/parity rehearsal и способ передачи семье первого
логина/пароля. Последний вопрос зафиксирован в
`vmshpwa/dev/development-plan/22-development-questions.md`.
