# Исправление ввода учёта преподавателей — 12 октября 2026

[Требование и реализация](../../../vmshpwa/docs/teacher-work.md).

Server-only read-only замеры ВМШ, без выгрузки production rows:
[пять распределений владельца](roster-production-counts.json),
[чтение inputs и поиск 448 Zoom-подписей](inputs-production-timing.json).
Проверены 8768 событий и 71 текущий teacher/admin. Первый текст: 22 точных
соответствия из 45 строк, 2 подсказки, 21 без совпадения. Новый поиск всех
Zoom-подсказок ~0.3 с против ~3.5 с; сохранение вообще не выполняет этот поиск.

`make pwa-check-fast PWA_E2E_MODES="teacher-work"` PASS: 3001 Python /
12 SKIP, 1119 frontend, 380 Storybook, 4 Chromium E2E, types/lint/format/i18n
и verification builds. [Квитанция](gate.json), [E2E](e2e.json).
Снимки осмотрены: [1280](screenshots/school-prefilled-1280.png),
[390](screenshots/school-prefilled-390.png), [dark](screenshots/teacher-work-dark-1280.png).
Браузер проверил отсутствие GET inputs и POST recalculation после alias command,
канонические варианты подписи, prefill, быстрый выбор и сохранение черновика
после reload. Отдельная Story проверила групповое исключение и подтверждение.
Выпуск на оба портала подготовлен. Изолированные регрессии проверяют точные имена,
инициалы и legacy-порядок, конфликты, опечатки, подтверждение/исключение,
канонические accepted receipts, replay и отсутствие автоматического расчёта.
