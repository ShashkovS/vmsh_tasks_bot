# Контекст задачи в вопросах

Staff показывает полный номер (занятие, группа, задача/подзадача) вместе с
названием в списке и карточке вопросов. В карточке раскрывается условие
только из опубликованной ready-версии condition: один problem по source_ordinal
и общее введение. Решения, правильные ответы и черновики не включаются.
При отсутствии публикации показано явное пустое состояние.

Реализация: `db_methods/pwa/support.py`, `apps/pwa_api/support_routes.py`,
`packages/contracts/src/support.ts`, `apps/staff/src/staff-support-pages.tsx`.
Документ загружается только с карточкой, не в списке. Существующие проверки
владельца и текущих назначений Staff сохранены.

Проверки: support repository/HTTP suites, support contract/client tests,
`staff-support-pages.test.tsx`, Staff TypeScript. Миграций и настроек нет.

Проверено: 15 существующих repository/HTTP тестов, затем 9 repository-тестов
с новой проверкой фильтрации условия; 10 frontend-тестов, Ruff и Staff TypeScript.
Браузерный сценарий в этом изменении не запускался.
