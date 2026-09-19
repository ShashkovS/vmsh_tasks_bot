# Phase 11: IDOR and role-boundary review

Дата: 30 июля 2026 года.  
Ревизия кода перед добавлением этого proof: `8fc7f13`.

Это ручной review серверных owner/scope/role границ и узкий
интеграционный прогон, а не внешний pentest.

## Что проверено

- Все audience API по умолчанию закрыты
  `pwa_authentication_middleware`; публичен только короткий явный
  allowlist auth/health/runtime. Это отдельно защищено
  `test_registered_audience_api_route_is_private_without_route_opt_in`.
- Student identity не принимается из body/query. Course, group и owner
  выводятся из перепроверенной сессии и текущих enrollment/access.
  Это покрывает курсы, занятия, test/written submissions, thread,
  reactions, questions, oral windows, classroom assignment, notifications,
  news и push subscription.
- Family сначала ищет `student_public_id` в актуальном
  `authenticated.family_children`. Только после этого читаются курс,
  home, progress, written thread и аудитория ребёнка.
- Teacher получает только read/review/oral/student capabilities и
  только в пределах текущих course/group grants. Review синонимов
  fail-closed, если хотя бы одна ветка вне scope. Перенос материала
  проверяет и исходную, и целевую задачу.
- Admin-only остаются content/checker, курсы и группы,
  schedule, synonym merge/split, classroom catalog/layout/assignment/delivery,
  news moderation, Telegram bindings, staff scopes, audit и bulk import.
  Admin staff-scope не повышает legacy-teacher до admin.
- Session/device routes и push/notification rows связаны с account/session из
  cookie, а не с переданным browser ID.

Статически просмотрены все route modules в `apps/pwa_api` (141
decorator registration в текущей ревизии), общая permission matrix в
`helpers/pwa/permissions.py` и default-private middleware в
`apps/pwa_api/middleware.py`.

## Исполненная матрица

Команда запускала 17 узких test modules на изолированном
`pwa-e2e` profile. Проверены:

- anonymous и cross-audience запросы;
- чужой child/course/group/problem/thread/review/queue item;
- teacher за пределами grant и teacher на admin-only endpoints;
- admin catalog/schedule/synonym/classroom/Telegram/staff-access boundaries;
- account-scoped notifications и push subscription;
- news по сумме course/group access.

Результат: `154 passed` за `44.59s`. Единственное
предупреждение — известный SymPy deprecation в зависимости
`mathsolvers`. Падений и пропусков нет.

## Остаточная граница

Часть Staff detail endpoints сначала находит объект по opaque
public ID, а затем проверяет teacher scope. Поэтому авторизованный
teacher в отдельных случаях может отличить nonexistent `404` от
existing-but-forbidden `403`. Содержимое объекта не возвращается,
запись не выполняется, public IDs не последовательны. Для текущей
модели лояльного небольшого Staff это принятый низкий риск, а не
повод для ещё одного слоя абстракций.

Student/Family owner-boundaries и admin-only записи fail closed. В рамках
этого review изменений runtime-кода не потребовалось.
