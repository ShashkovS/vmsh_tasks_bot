# Компактные действия проверки — 17 ноября 2026

Коммит `c6e0e19c8da8c9e965f370bf3dcc26a5af0d7f32` выпущен только на
**vmshfirstvds**, static release `mobile-review-actions-20261117`.
[Решение и файлы реализации](../../../vmshpwa/docs/review-workflow.md#уточнение-17-ноября-компактные-действия-и-внешние-поля).

Мобильные страницы очереди, истории, простыни и отдельной проверки используют
внешние поля содержимого `px-1`. Шапка страницы сохраняет суммарно 16 px через
новый необязательный `PageLayout.headerClassName`; его значения по умолчанию
и глобальная шапка приложения не изменились. Серия сохраняет тот же ритм.

Убран повторный абзац о цифровых клавишах под оценками; фразы о работе клавиш
в комментарии удалены. Подсказка «⌘/Ctrl + Enter — отправить.» стоит справа от
кнопки. «В другую задачу» и «Клонировать в…» помещаются рядом на телефоне.
Клавиатурное поведение сохранено. RU/EN каталоги обновлены через
`make pwa-i18n-extract`; существующие unit/E2E селекторы используют новые подписи.

## Проверки

`make pwa-check-fast PWA_E2E_MODES="review"` остановился на прежних замечаниях
форматтера вне начальной правки. Остальные шаги продолжены теми же командами
`check_runner.py` и изолированным профилем, без повторения прошедших наборов.
Затем затронутый `PageLayout` также отформатирован. Полный gate **не PASS**:
неизменённые файлы с замечаниями форматтера не переписывались.

- Types, JS/CSS lint, frontend/backend i18n, verification build PASS.
- Python: 3134 PASS, 15 SKIP, 2 прежних FAIL вне правки:
  `test_piece_scales_with_tikz_picture` и
  `test_guard_rejects_a_correlated_full_scan_and_accepts_indexed_lookup`.
- Frontend: 1152 PASS; Storybook: 386 PASS.
- Chromium review E2E: все 5 PASS, включая transfer/clone, Ctrl+Enter,
  восстановление черновиков, конфликт простыни и повторную проверку.
- Chromium/Firefox/WebKit, 320 и 390 px, светлая и тёмная темы: подсказка справа
  от отправки, лишние фразы отсутствуют, overflow отсутствует. Отступ заголовка
  очереди 16 px во всех движках. Снимки сделаны без незавершённых CSS-переходов.
- Реальная простыня 390 px, обе темы: снимки просмотрены; короткие кнопки рядом.

[Gate receipt](checks.json), [browser geometry](browser-proof.json),
[форма light](form-chromium-390-light.png), [форма dark](form-chromium-390-dark.png),
[320 px](form-webkit-320-dark.png), [шапка очереди](queue-chromium-light.png),
[простыня](sheet-mobile-light.png).
Полные логи: `.runtime/vmshpwa/checks/20261117-mobile-review-actions/`.

## Выпуск

[Точечный патч](ui.patch) применён к текущему production frontend source,
сохранённому предыдущим выпуском. Frozen зависимости, production builder,
immutable package/asset verify; атомарная смена `vmshpwa/current` после проверок.
Сверены [хеши всех 16 изменённых UI source/catalog файлов](ui-hashes.json).
FirstVDS media-policy и каноническая конфигурация сохранены. Backend checkout,
SQLite и службы не менялись, рестартов и миграций нет; прежний static release
доступен для отката. GlitchTip DSN и штатный режим без private upload credentials
сохранены, public sourcemaps отсутствуют.

25 публичных HTTP checks, 4 HTML и 120 Staff JS/CSS hash checks PASS.
[Production proof](production-proof.json), [HTTP smoke](http-smoke.log).
[Подготовка](deploy.py) и [активация с откатом](activate.py) — одноразовые записи,
не инструкция повторять их на текущем релизе. Серверные исходники и логи:
`/web/vmsh_tasks_bot/deploy/releases/mobile-review-actions-20261117/`.
