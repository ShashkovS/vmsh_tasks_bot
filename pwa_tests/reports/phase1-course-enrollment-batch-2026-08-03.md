# Phase 1 proof: batch-зачисление на курсы

Дата: 3 августа 2026 года.

## Проверяемый результат

Staff admin после отдельных Student и Family batch может вставить
TSV `login, course, allowed_groups`, получить preview и одним действием
создать `course_enrollments`, интервалы `course_group_access` и
append-only `course_enrollment_events`.

- Active group выбирается из allowed groups по `groups.sort_order`, не
  по порядку TSV. Tie-break: `short_code`, затем legacy `group_id`.
- Все allowed groups в preview и UI показаны в том же product order.
- Для текущего курса порядок: «Начинающие» = 1,
  «Продолжающие» = 2, «Эксперты» = 3. Это данные, а не зашитый
  список; другие курсы могут задать свой порядок.
- Новое enrollment получает mode `online`.
- Первое enrollment школьника синхронизирует legacy
  `users.group_id/allowed_groups`, чтобы Telegram-бот продолжал работать.
  Дополнительные курсы эти одиночные legacy-поля не перезаписывают.
- Teacher получает `403`. Повторное enrollment, неизвестные или
  archived course/group и невалидные строки показываются до apply.
- Apply заново читает SQLite в одной transaction. Если между preview и
  apply изменился состав или order групп, возвращается `409
  preview_changed`; частичная запись не выполняется.

## Границы реализации

- Pure normalization/order policy:
  [`models/pwa/account_batches.py`](../../models/pwa/account_batches.py).
- Короткие SQLite-операции:
  [`db_methods/pwa/account_batches.py`](../../db_methods/pwa/account_batches.py).
- aiohttp preview/apply и админские error messages:
  [`apps/pwa_api/account_batch_routes.py`](../../apps/pwa_api/account_batch_routes.py).
- Zod contracts:
  [`vmshpwa/packages/contracts/src/account-provisioning.ts`](../../vmshpwa/packages/contracts/src/account-provisioning.ts).
- Real API client:
  [`vmshpwa/packages/app-shell/src/admin-course-client.ts`](../../vmshpwa/packages/app-shell/src/admin-course-client.ts).
- Staff TSV/UI:
  [`vmshpwa/apps/staff/src/account-provisioning-page.tsx`](../../vmshpwa/apps/staff/src/account-provisioning-page.tsx)
  и
  [`account-provisioning-tsv.ts`](../../vmshpwa/apps/staff/src/account-provisioning-tsv.ts).

## Доказательства

- Python domain/real-aiohttp integration: `14 passed`; в том числе reverse TSV
  order, `403`, transaction records, legacy sync и `409` при смене
  `groups.sort_order`.
- Frontend unit: Zod contract, TSV parser, API client.
- Storybook interaction/a11y:
  `pages-staff-account-provisioning--course-enrollment-preview-and-apply`.
  Story вставляет `э, н, п`, а preview показывает active `н` и ordered
  allowed `н, п, э`.
- Visual snapshots не обновлялись. Ручной visual approval не
  зафиксирован: local in-app browser не смог подключиться к уже
  работающему human Storybook из-за CDP timeout. Это не маскируется
  как visual acceptance.

- Targeted Python: `14 passed` на восьми pytest workers.
- Full PWA Python в sandbox: `17 failed, 1424 passed, 6 skipped, 205 errors`;
  run не является gate, потому что sandbox запретил aiohttp и gateway
  tests открывать loopback sockets (`PermissionError`), вызвав setup errors и
  каскадные failures. Повторный unsandboxed run отклонён execution
  environment и остаётся follow-up; как зелёный full gate он не
  записан.
- Full frontend unit: `116` files, `606 passed`.
- Targeted Storybook interaction/a11y: `1` file, `3 passed`; full browser run в
  sandbox не стартовал из-за `listen EPERM ::1` и остаётся follow-up.
- Direct TypeScript checks для contracts, app-shell и Staff: passed.
- Full ESLint + Stylelint: passed. Prettier exact touched frontend files: passed.
- Production build всех трёх apps, включая Student/Family injectManifest:
  passed.
- `git diff --check`: passed после финальной правки.
