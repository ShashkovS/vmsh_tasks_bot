# Phase 9: course achievements in Family PWA

Дата проверки: 3 августа 2026 года.

## Проверяемый результат

- Family home показывает уже рассчитанные достижения отдельно внутри каждого
  курса ребёнка.
- Student и Family используют один маленький словарь русских подписей в
  `packages/product/src/course-achievements.ts`; rule codes и даты остаются
  данными API, а локализованный текст не попадает в SQL.
- Неизвестный будущий rule code безопасно скрывается до появления согласованной
  подписи. UI не показывает внутренний код и не придумывает пользователю текст.
- Блок содержит только личные факты ребёнка. Рейтинг, место, процентиль и
  сравнение с группой отсутствуют.
- API integration проверяет настоящий путь SQLite → Family home для
  `first_submission`, а Storybook использует production-компонент
  `FamilyCourseAchievements`.

## Файлы и Storybook

- `vmshpwa/packages/product/src/course-achievements.ts` — общие подписи;
- `vmshpwa/apps/student/src/student-progress-page.tsx` — Student consumer;
- `vmshpwa/apps/family/src/family-children-page.tsx` — Family consumer;
- Storybook: `Pages/Family--course-achievements`;
- API regression:
  `pwa_tests/integration/test_phase9_family_courses.py::test_family_home_returns_only_browser_ready_current_lessons`.

## Автоматические доказательства

```text
Focused Python Phase 9 migration/domain/Family integration
  10 passed

Shared label unit tests
  2 passed

Pages/Family browser interaction + addon-a11y
  12 passed

Full Storybook interaction + addon-a11y
  50 files / 242 passed

Full frontend unit
  112 files / 590 passed

Full PWA Python (8 workers, local aiohttp sockets)
  1568 passed / 6 intentional skips

ESLint, Stylelint, strict TypeScript, Student/Family/Staff production builds
  pass
```

Streak и достижение за завершённое занятие остаются отдельными незакрытыми
Phase-9 правилами. Visual snapshots не обновлялись; story ещё требует ручного
визуального принятия владельцем.
