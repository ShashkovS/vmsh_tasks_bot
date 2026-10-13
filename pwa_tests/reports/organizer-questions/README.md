# Вопросы организаторам — проверка 11 сентября 2026

Реализован [принятый план](../../../vmshpwa/docs/organizer-questions.md).
Student и Family создают отдельные личные обращения с текстом и фотографиями.
Администраторы отвечают через Staff → Вопросы → Вопросы организаторам.
Преподаватели и другие члены семьи не получают доступа к переписке и вложениям.

## Проверки

- Backend: **14 passed** — шесть сценариев обращений плюс регрессии учебных вопросов
  и их уведомлений. Проверены права, второй родитель, необязательный ребёнок,
  отозванная связь, отсутствие зачисления, повторная отправка, атомарность,
  пагинация, повреждённые фотографии и ограничение размера.
- Миграция на копии заполненной тестовой базы: **1 passed**. Данные пользователей,
  аккаунтов, семейных связей, зачислений и учебной переписки не изменяются;
  `foreign_key_check` чистый.
- Unit: **5 passed** — контракт запросов, бинарные черновики и их изоляция,
  сохранение идентификаторов загрузки, очистка после подтверждения, регрессии
  настроек Student/Family.
- Production E2E: **9 passed, без повторов**, 33.7 s — Chromium, WebKit, Firefox.
  В каждом движке проверены школьник, родитель и запрет преподавателю.
  Реальный aiohttp, SQLite, конвертация фото и WebSocket; без MSW и внешних сервисов.
- Все три приложения: TypeScript и production build прошли. Tools typecheck,
  scoped ESLint и Ruff прошли. Тёмная тема переключалась кнопкой приложения.

Основной сценарий: вход с экрана «Сейчас» → текст + фотография → восстановление
черновика после reload → ошибка без сети → повтор → ответ администратора с фото →
живое обновление → счётчик в профиле → история → переход из уведомления →
ответ с клавиатуры. Проверены 320/390 px, desktop, тёмная тема и 200% zoom.

Команды:

```sh
.venv/bin/pytest -q -n0 pwa_tests/integration/test_organizer_questions.py pwa_tests/integration/test_support_thread_http_api.py pwa_tests/integration/test_phase8_support_notifications.py
# После добавления отдельного rehearsal миграции:
.venv/bin/pytest -q -n0 pwa_tests/integration/test_organizer_questions.py -k migration
pnpm --dir vmshpwa exec vitest run --project unit packages/contracts/src/organizer-questions.test.ts packages/offline/src/organizer-draft.test.tsx apps/student/src/student-profile-page.test.tsx apps/family/src/family-enrollment-settings.test.tsx
make pwa-e2e-organizers
```

## Снимки

| Браузер  | Школьник, 320 px                              | Родитель, 390 px                             | Тёмная тема                                    | Desktop                                          | 200%                                         | Ответ Staff                                    |
| -------- | --------------------------------------------- | -------------------------------------------- | ---------------------------------------------- | ------------------------------------------------ | -------------------------------------------- | ---------------------------------------------- |
| chromium | [Снимок](chromium-organizers-student-320.png) | [Снимок](chromium-organizers-family-390.png) | [Снимок](chromium-organizers-student-dark.png) | [Снимок](chromium-organizers-family-desktop.png) | [Снимок](chromium-organizers-family-200.png) | [Снимок](chromium-organizers-family-staff.png) |
| webkit   | [Снимок](webkit-organizers-student-320.png)   | [Снимок](webkit-organizers-family-390.png)   | [Снимок](webkit-organizers-student-dark.png)   | [Снимок](webkit-organizers-family-desktop.png)   | [Снимок](webkit-organizers-family-200.png)   | [Снимок](webkit-organizers-family-staff.png)   |
| firefox  | [Снимок](firefox-organizers-student-320.png)  | [Снимок](firefox-organizers-family-390.png)  | [Снимок](firefox-organizers-student-dark.png)  | [Снимок](firefox-organizers-family-desktop.png)  | [Снимок](firefox-organizers-family-200.png)  | [Снимок](firefox-organizers-family-staff.png)  |

Проверены снимки мобильной переписки, фотографий, двух тем, увеличенного масштаба
и ответа администратора. В отчёте сохранены 18 снимков финального прогона.

## Выпуск

Перед запуском нового кода требуется миграция `0088.pwa_organizer_questions`.
Старый Telegram SOS не переносится и не пересылается в новый интерфейс.
Проверки работали только с изолированными тестовыми данными. Владелец разрешил
commit и push 11 сентября 2026. Развёртывание не выполнялось.
