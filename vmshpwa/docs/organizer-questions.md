# Вопросы организаторам

Принятый план, 11 сентября 2026. Независимые обращения школьника/родителя,
владелец — auth_accounts. Видят только автор и global admin. Необязательный
ребёнок родителя проверяется при создании; последующая потеря связи не скрывает
собственную историю. Текст и до 10 JPEG/PNG/WebP по 25 МиБ; новые обращения
без темы. Статус определяется последним сообщением, без закрытия и назначения.

Student/Family: `/organizers`, `/organizers/new`, `/organizers/$threadId`;
ссылки на «Сейчас» и в профиле, без расширения нижней навигации.
Staff: вкладка «Организаторам» в вопросах, очередь «Нужен ответ» по умолчанию.
API: `/{audience}/api/v1/organizer-questions`, отдельные GET списка/переписки,
POST создания/сообщений/вложений/read; account-scoped invalidation и уведомления.
Пагинация по 50, защищённые фотографии, локальные черновики с бинарными ArrayBuffer в IndexedDB.

Реализация: [миграция](../../migrations/0088.pwa_organizer_questions.sql),
[домен](../../models/pwa/organizer_questions.py),
[SQL](../../db_methods/pwa/organizer_questions.py),
[HTTP](../../apps/pwa_api/organizer_question_routes.py).
Старый Telegram SOS и учебные support_threads не меняются.

## Проверка

Реализовано локально. Backend 14 passed + 1 migration rehearsal, unit 5 passed,
E2E 9 passed в Chromium/WebKit/Firefox; TypeScript, ESLint, Ruff и production build
прошли. [Отчёт и 18 снимков](../../pwa_tests/reports/organizer-questions/README.md).

Frontend: [общая композиция](../packages/app-shell/src/organizer-pages.tsx),
[API-клиент](../packages/app-shell/src/organizer-client.ts),
[контракты](../packages/contracts/src/organizer-questions.ts),
[бинарные черновики](../packages/offline/src/organizer-draft.ts).
Ссылки стоят на «Сейчас» и в профиле Student/Family; админская очередь находится
в `/staff/questions/organizers`. Непрочитанные уведомления и счётчик обращений
сходятся после просмотра; новые сообщения инвалидируют только аккаунт автора
и глобальных администраторов. Фотографии не перезаписываются в IndexedDB при
каждом вводе текста. Повтор отправки использует сохранённые ID загруженных фото.

[Backend-тесты](../../pwa_tests/integration/test_organizer_questions.py) и
[E2E](../e2e/organizer-questions.spec.ts) проверяют границы и сценарии плана.
Изолированная база и storage; миграцию необходимо применить перед выпуском.
