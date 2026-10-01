# Генерация metadata курса

Язык генерируемых названий, приглашений к вводу, сообщений о неверном ответе,
поздравлений и редакционных замечаний определяется `default_locale` выбранного
[профиля бренда](branding.md). Язык интерфейса конкретного сотрудника не меняет
язык контента. Английский профиль использует английские инструкции обоих проходов,
описания JSON Schema, примеры и сообщения повторной попытки. Встроенные тексты
`btitle/bvalerr/bwrong/bcongrat` переводит модель; математические ответы, варианты
выбора и структурные идентификаторы сохраняются как данные исходной задачи.

В «Курсы → Каталог → Настройки курса» поле «Модель OpenRouter для metadata»
принимает идентификатор вида `provider/model`, включая новые модели без изменения
списка в коде. По умолчанию остаётся `openai/gpt-5.6-luna`. Значение применяется
при следующей генерации, включая фактологическую проверку, без перезапуска.
Старый клиент, не передавший поле, сохраняет прежнюю модель при редактировании.

Сохранение настройки использует существующие права администратора, `If-Match`
и аудит курса. Генерация по-прежнему возвращает черновик для проверки Staff;
публикация требует отдельного сохранения metadata.

Реализация: [миграция 0104](../../migrations/0104.course_metadata_model.sql),
[модель настройки](../../models/pwa/metadata_generation.py),
[SQL каталога](../../db_methods/pwa/course_catalog.py),
[API курса](../../apps/pwa_api/admin_course_routes.py),
[API генерации](../../apps/pwa_api/content_routes.py),
[адаптер](../../helpers/pwa/content/metadata_generation.py),
[OpenRouter-контракт](../../vmsh_openrouter_tools_fixed_v2/vmsh_openrouter_contract.py),
[редактор курса](../apps/staff/src/course-catalog-editors.tsx).


## Проверка 1 октября 2026

- `pytest -o addopts='' pwa_tests/domain/test_metadata_generation.py
  pwa_tests/domain/test_metadata_generation_language.py
  pwa_tests/integration/test_course_metadata_model.py
  pwa_tests/integration/test_phase10_course_catalog.py
  pwa_tests/integration/test_content_http_api.py -q`: 90 PASS; отдельно
  `pwa_tests/test_schema_inventory.py`: 21 PASS на актуальной основе с 0105.
  Проверены default/stored model, независимость языка
  бренда от cookie, live-смена модели, права, конфликт версии, аудит, старые клиенты,
  исправления JSON, английские image/checker сообщения и неизменность ответов.
- Frontend: 24 Vitest PASS в editor/contract/admin-client; Staff/tools TypeScript,
  ESLint, Ruff, синхронность/полнота переводов frontend/backend и Staff build PASS.
- [Stories редактора](../apps/staff/src/course-catalog-editors.stories.tsx): Chromium,
  русский/английский интерфейс, светлая/тёмная тема, валидный и неверный ID модели.
  Скриншоты локально в `.runtime/vmshpwa/metadata-settings-proof/`; pageerror нет.
- Настоящие OpenRouter-запросы и production-выкладка не запускались. При выкладке
  применяется миграция 0104. Сохранённые ранее metadata меняются только при
  явно запущенной пользователем перегенерации и последующем сохранении черновика.
