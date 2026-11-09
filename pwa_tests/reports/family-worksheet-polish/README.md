# Родительский кабинет: проверка

[Требования](../../../vmshpwa/docs/family-worksheet-polish.md).

- **8 backend-тестов**: `pwa_tests/integration/test_phase9_family_courses.py`, включая совпадение оценок с Student, запрет чужого ребёнка/группы, просмотр разрешённой неактивной группы, отсутствие материалов переписки в ответе и существующие сценарии зачисления.
- **6 unit-тестов**: Family course client и настройки зачисления.
- **6 E2E**, Chromium/WebKit/Firefox: [родительские листки](../../../vmshpwa/e2e/family-worksheet-polish.spec.ts) и сценарий `child caches` из [family-context](../../../vmshpwa/e2e/family-context.spec.ts). Проверены ширина страницы ребёнка, раскрытая история в обратном порядке, ссылки профиля, старое занятие, группы, оценки, изображения, отсутствие сдачи/переписки, 320/390 px без горизонтального переполнения, тёмная тема. Существующее изменение группы/формата с подтверждением и разделение детей сохранены.
- Workspace/tools typecheck, сборка всех приложений, ESLint изменённых frontend-файлов прошли. Тесты запускаются через `exclusive_e2e_run` / `run_commands` с реальным изолированным backend; production не изменялся.

В прежнем разрешении ссылки использовалось только `currentLesson` активной группы. Новый GET `/family/api/v1/children/{studentId}/courses/{courseId}/lessons/{number}?group={groupId}` разрешает выбранное опубликованное занятие и возвращает общий Student read model оценок. Просмотр не меняет зачисление и не загружает переписку. Миграции не требуются.

| Браузер | Ребёнок | Профиль | Листок 320 px | Листок 390 px | Тёмная тема |
| --- | --- | --- | --- | --- | --- |
| Chromium | [Снимок](chromium-child-desktop.png) | [Снимок](chromium-profile.png) | [Снимок](chromium-worksheet-320.png) | [Снимок](chromium-worksheet-390.png) | [Снимок](chromium-worksheet-dark.png) |
| WebKit | [Снимок](webkit-child-desktop.png) | [Снимок](webkit-profile.png) | [Снимок](webkit-worksheet-320.png) | [Снимок](webkit-worksheet-390.png) | [Снимок](webkit-worksheet-dark.png) |
| Firefox | [Снимок](firefox-child-desktop.png) | [Снимок](firefox-profile.png) | [Снимок](firefox-worksheet-320.png) | [Снимок](firefox-worksheet-390.png) | [Снимок](firefox-worksheet-dark.png) |
