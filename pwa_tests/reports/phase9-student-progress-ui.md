# Phase 9: production-экран личного прогресса Student

Дата проверки: 2026-07-29.

## Проверяемый результат

- `/student/progress` больше не использует prototype-данные страницы.
- Список курсов и персональная сводка загружаются через настоящий Student API и
  валидируются Zod-контрактом.
- Выбранный курс хранится в проверяемом URL search parameter `course`.
- Экран показывает accepted/partial/needs-work totals, занятия и дни работы
  только самого школьника. Полей cohort, distribution, percentile и position в
  контракте нет.
- Есть loading, empty, offline, error и forbidden состояния.

## Автоматические доказательства

```text
contracts + course client + offline decorator
  15 passed

ESLint / strict TypeScript
  pass

Student production build
  pass; injectManifest service worker generated
```

Сводка пока сознательно не кешируется для offline: offline reading условий и
черновиков остаётся неизменным, а progress повторно читается после появления
сети. Visual snapshots не создавались и не обновлялись.

## Файлы

- `vmshpwa/packages/contracts/src/progress.ts`;
- `vmshpwa/packages/app-shell/src/course-client.ts`;
- `vmshpwa/apps/student/src/student-progress-page.tsx`;
- `vmshpwa/apps/student/src/routes/progress.tsx`.
