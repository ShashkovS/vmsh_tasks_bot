# Мобильные поля проверки — 17 ноября 2026

Выпущен коммит `b2df728b837ad5b8450fa64ca5d6255433359595` только на
**vmshfirstvds**, релиз `mobile-review-20261117`.
[Требование и реализация](../../../vmshpwa/docs/review-workflow.md#17-ноября-2026--поля-и-переносы-в-мобильной-проверке).

До 640 px сообщения Staff используют доступную ширину вместо ограничения 85%;
вложенные поля серии, карточки работы и простыни уменьшены. У текста решения
и комментария `hyphens: auto`, у UI и полей ввода обычный набор.

## Проверки

Запущен `make pwa-check-fast PWA_E2E_MODES="review submissions"`. Он остановился
на 13 замечаниях Prettier в неизменённых файлах. Изменённые файлы отформатированы;
остальные этапы продолжены теми же командами и изолированным профилем из
`check_runner.py`, без повторения уже успешных наборов. После исправления
optional-пропа layout строгая типизация повторно прошла.

- Types, JS/CSS lint, frontend/backend i18n и production-like E2E build PASS.
- Python: 3134 PASS, 15 SKIP, 2 FAIL вне изменённого кода:
  `test_guard_rejects_a_correlated_full_scan_and_accepts_indexed_lookup` и
  `test_piece_scales_with_tikz_picture`.
- Frontend: 1152 PASS; Storybook: 385 PASS.
- Chromium review/submissions: 7 PASS, 1 FAIL. Все 5 review-сценариев прошли.
  В `Phase 4: a test answer survives reload and an offline POST is delivered
  exactly once` таймаут при ожидании Student POST `/auth/login`, до отправки
  ответа. Полный gate **не объявлен зелёным**.
- Длинное решение в Chromium/Firefox/WebKit при 390 px: `hyphens=auto`,
  переполнения нет, текст занимает ширину контейнера за вычетом 18 px границ
  и полей сообщения. Светлая/тёмная темы просмотрены. Storybook добавляет свои
  внешние поля вокруг примера; это не поля страницы Staff.
- Мобильная простыня Chromium, обе темы: снимки просмотрены, переполнения нет.

[Результаты gate](checks.json), [геометрия в браузерах](browser-proof.json),
[Chromium](chromium-light.png), [WebKit dark](webkit-dark.png),
[простыня light](sheet-mobile-light.png), [простыня dark](sheet-mobile-dark.png).
Полные логи: `.runtime/vmshpwa/checks/20261117-mobile-review-final/` и
`20261117-mobile-review-continuation/` (ранние static steps).

## Выпуск

Сборка из сохранённого production frontend source FirstVDS с точечным
[патчем](ui.patch). Хеши шести UI-файлов сверены с локальным коммитом;
FirstVDS media-policy сохранена (SHA-256 в квитанции). Зависимости установлены
по frozen lockfile; Node 26 / pnpm 11.15.1. Штатный production builder, проверка
provenance, immutable package verify и удержание старых assets перед атомарной
сменой `vmshpwa/current`. Канонические настройки и backend checkout не менялись,
службы не перезапускались, миграций нет. Предыдущий статический релиз сохранён.

25 HTTP checks PASS, HTML четырёх приложений и все 120 Staff JS/CSS хешей
совпали с новым релизом. Maintenance off, public sourcemaps отсутствуют.
GlitchTip DSN сохранён; upload credential на FirstVDS отсутствует, поэтому
production builder использовал штатный fallback без загрузки private maps.

[Production proof](production-proof.json), [HTTP smoke](http-smoke.log),
[подготовка](deploy.py), [активация с автоматическим откатом](activate.py).
Это одноразовые записи выпуска, не инструкция повторять их на текущем сервере.
Серверные source/build/dependency logs и rollback target доступны под
`/web/vmsh_tasks_bot/deploy/releases/mobile-review-20261117/`.
