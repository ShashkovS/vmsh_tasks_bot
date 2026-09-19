# Phase 10: каталог 1500 школьников

Дата проверки: 30 июля 2026 года.

## Что проверено

- SQLite одним снимком читает 1500 школьников, их активные записи на курс,
  доступ к группам, web-аккаунты, силу и 1500 связей с семейными аккаунтами.
- Три прямых запроса используют существующие индексы
  `auth_accounts_linked_user_audience_uq`,
  `course_group_access_enrollment_history_idx` и
  `family_student_links_student_revoked_idx`; временные automatic indexes не
  создаются.
- Staff не создаёт 1500 DOM-строк: список виртуализирован уже имеющимся
  `@tanstack/react-virtual`, а поиск продолжает работать по полному снимку.

## Результаты

```text
Phase-10 SQLite characterization:
  1500 students + 1500 enrollments + 1500 group access rows
  + 1500 Family links: 0.025 s
  pytest: 1 passed

Storybook browser mode, apps/staff/src/pages.stories.tsx:
  20 passed

Phase-10 directory + enrollment HTTP regression:
  6 passed
```

Story `pages-staff--student-directory-1500` проверяет исходный счётчик 1500,
ограниченное число отрисованных строк и поиск школьника в конце набора.
Порог Python-теста `3 s` — только широкий regression tripwire для
разработческого компьютера, не production SLO.

## Файлы доказательства

- `pwa_tests/integration/test_phase10_directory_performance.py`;
- `vmshpwa/apps/staff/src/staff-student-directory-page.tsx`;
- `vmshpwa/apps/staff/src/pages.stories.tsx`.
