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
- Настоящие OpenRouter-запросы в проверках не запускались. Production-выкладка
  завершена ниже. Сохранённые ранее metadata меняются только при
  явно запущенной пользователем перегенерации и последующем сохранении черновика.


## Production — 1 октября 2026

Релиз `a13c01ba3f7fe60c691cfd04d37faf55f04ec8a3` отправлен в `vmshpwa` и
установлен на обоих серверах по запросу владельца. VMSH использовал штатный
webhook; TLF — подготовленный SSH-скрипт с отдельной frozen-сборкой и репетицией
миграции на серверной копии перед остановкой PWA/Zoom/analytics writers.
Зависимости и runtime-конфигурация не менялись. Миграция 0104 применена на обоих
серверах; каждая база содержит 77 migrations.

- VMSH: static release `a13c01ba3f7f-20261001122046`; before/after backups
  `vmsh-before-deploy-20261001122152.sqlite3` /
  `vmsh-after-deploy-20261001122220.sqlite3`, integrity ok. Сравнение подтвердило
  неизменность course/attendance flags и всех 1519 enrollment rows. PWA, Telegram
  и analytics timer active; webhook подтвердил frontend/backend/migrations.
- TLF: static release `tlfprep-20261001-metadata-a13c01ba3f7f`; retained script,
  rollback и проверки в `/web/vmsh_tasks_bot/deploy/releases/` с тем же release ID.
  Before/after backups `20261001T122056.638841Z` /
  `20261001T122125.045072Z`, integrity ok. Все прежние product-table rows,
  секретная конфигурация и NATS PID совпали; три raw Zoom receipts сохранены.
  Оба курса остаются online-only. PWA 2 workers, Zoom 1 worker, analytics active.
- На каждом портале прошли 25 публичных read-only HTTP checks и backend health.
  В существующих owner-authenticated браузерных сессиях проверен каталог и
  открыта живая форма Course settings: поле `OpenRouter model for metadata`
  отображает `openai/gpt-5.6-luna`. Настройки через UI не сохранялись.
- TLF brand `default_locale=en`, VMSH `default_locale=ru`; для всех существующих
  курсов сохранён текущий default model. Переход на другую модель выполняется
  владельцем через поле настройки курса после её тестирования.

Откат TLF использует только rollback миграции `0104.course_metadata_model` через
yoyo при остановленных writers, затем retained source SHA и прежний static
symlink. Production DB snapshot не подменяется. Сборки и проверки не создавали
metadata, submissions или synthetic Zoom events в production.


## English TeX generation failure — 1 October 2026

The TLF worksheet `gl-1` / `cr-3` failed before calling OpenRouter: the adapter
required a Russian worksheet/group identifier and the legacy parser only knew
Russian structural commands. The worksheet uses `problem/eproblem`,
`answer/eanswer`, `solution/esolution`, `suggestion/esuggestion` and English
`Sect` headings, with teacher fields inside each problem.

[`_contract_latex`](../../helpers/pwa/content/metadata_generation.py) now reuses
the compiler's [dialect vocabulary/scanner](../../helpers/pwa/content/dialect.py)
to adapt semantic tokens for the markup contract. Math, comments, declarations
and drawings stay intact; stored TeX is unchanged. A worksheet without legacy
number/group uses a private contract identity: `_normalize_reference_markup`
still validates and returns only canonical server problem IDs and numbers.
[The contract parser](../../vmsh_openrouter_tools_fixed_v2/vmsh_openrouter_contract.py)
recognizes English section types and extracts teacher fields inside or after
the problem without counting answer subitems as separate tasks. The actual TLF
source parses to five tasks, all answers/hints/solutions, and zero warnings.

[Service transport](../packages/contracts/src/service-availability.ts) now
returns validated application error envelopes unchanged, including 502/503/504,
instead of swallowing their localized explanation or replaying a generation
request. Marked maintenance and ambiguous gateway/network failures retain
existing recovery behavior. [App-shell](../packages/app-shell/src/service-availability.tsx)
provides the current Lingui translation for `request_not_confirmed`; the old
Russian/English concatenated text is removed.

Verification: 29 metadata/domain tests, 13 transport tests, affected TypeScript,
ESLint/Ruff, i18n sync/coverage and Staff build pass; both HTTP metadata
regression scenarios pass. A real production generation passed as recorded below.
No database migration or course model changes are required.


### Verified production recovery

Fix `662e3f036c9c32175d64d472d3616af6b4f8dc57` is deployed on both hosts.
VMSH webhook completed with backend/frontend changes and no migration; static
release `662e3f036c9c-20261001140928`. TLF used the reviewed SSH script retained
in `/web/vmsh_tasks_bot/deploy/releases/` under release
`tlfprep-20261001-metadata-recovery-662e3f036c9c`. Its before/after backups
`20261001T140937.795222Z` / `20261001T141003.631368Z` passed integrity; all product
rows (including course metadata models), credentials and NATS PID were identical
with writers stopped. Both hosts pass 25 public read-only HTTP checks and health.
No schema or service configuration changes were required.

In the existing owner-authenticated Staff session, the actual `gl-1` / `cr-3`
Generate metadata action succeeded with the currently selected
`openai/gpt-6-luna`. Server request `ff381658d5cc4663865f5dfa0a136aa8` returned
HTTP 200 in 47.13 seconds at 2026-10-01 17:12:36 Europe/Moscow. The UI showed
“Metadata draft updated”, five English titles, English format prompts and
wrong/correct-answer feedback. The remaining checker review note for problem 2
is English and is an intentional manual-review requirement. Save metadata was
not invoked: the generated result stays a local review draft and the server's
problem configuration/publications are unchanged.

Local screenshot proof:
`.runtime/vmshpwa/metadata-recovery-proof/tlf-success.jpg`. Focused verification
total: 29 domain tests, 2 HTTP scenarios and 13 transport tests (all pass),
plus types/lint/i18n/build and parsing the actual English worksheet.


## Типы задач из таблицы — 1 октября 2026

Требование владельца: смешанный листок может содержать письменные, устные
и тестовые задачи без разделов, позволяющих парсеру определить способ сдачи.
В Staff измените столбец «Тип задачи» и нажмите «Сгенерировать с типами из
таблицы» / «Generate using table types». До генерации сохранять таблицу не
нужно. Обычная кнопка сохраняет автоматический выбор типов из исходника.
Все остальные поля перегенерируются; результат проверяется и сохраняется
обычным действием. Отмена подтверждения и ошибка запроса сохраняют черновик.

`ProblemReviewWorkflow` читает текущие строки, в том числе изменения после
генерации и без доступного localStorage. `ContentApiClient.generateMetadata`
передаёт необязательный `problemTypes: [{problemId, problemType}]`; Zod контракт
и HTTP-граница проверяют типы 1/2/3, уникальность и полное покрытие текущей
revision. Отсутствие поля сохраняет совместимость со старым клиентом.

`MetadataGenerationTarget.problem_type` связывает выбранный тип с canonical
строкой. `generate_lesson_json` применяет полный `problem_type_overrides` до
построения первого prompt и использует его же в фактологической проверке и
нормализации. Разделы и встроенный `bptype` не отменяют явно выбранный тип;
каждый подпункт независим. Для смешанного родительского условия machine parse
не передаёт противоречащий общий тип. Генерация не пишет конфигурацию задач
и не требует миграции или изменения настройки модели.

Проверки: `test_metadata_generation_language.py` — оба прохода и смешанные
подпункты вопреки разделу/bptype; `test_content_http_api.py` — необязательные
типы, scope, полнота, дубли, недопустимые коды и неизменность сохранённых данных;
`problem-review-generation.test.tsx` — реальная таблица, несохранённые правки,
недоступный localStorage, повторная генерация и отмена; contract/client tests.
Проверены 31 domain-сценарий, 2 HTTP-сценария, 40 UI/contract/client tests,
typecheck contracts/content/Staff, ESLint/Ruff, i18n sync/coverage и Staff build.
Итоговый production-выпуск и проверка завершены ниже.


Дополнение: восстановление local draft в `ProblemReviewWorkflow.acceptMetadata`
имеет приоритет над переходом в «metadata подтверждены». Уже проверенная серверная
таблица не удаляет несохранённые типы и остальные поля при reload; старый ETag
по-прежнему отмечает черновик как stale. Отдельный interaction-тест проверяет
восстановление и передачу этих типов после перезагрузки.

Основной `de054345` выложен на VMSH webhook (frontend/backend, no migrations)
и TLF SSH release `tlfprep-20261001-explicit-types-de054345c13a`. TLF прошёл 25
read-only HTTP checks; все product rows, credentials и NATS PID сохранились.
Backup: `20261001T150339.467376Z` / `20261001T150405.605579Z`, integrity ok.
Дополнение `6e4b82f76f6366dce376bf977ac5f9ed07c9330d` выложено на оба сервера.
TLF release: `tlfprep-20261001-explicit-types-6e4b82f76f63`; retained script
и проверки сохранены под тем же именем в `/web/vmsh_tasks_bot/deploy/releases/`.
Before/after backup: `20261001T151024.052471Z` / `20261001T151049.947421Z`,
integrity ok, 3 raw Zoom receipts. Product rows, credentials и NATS PID совпали.
Оба сервера — по 25 read-only HTTP checks. VMSH webhook подтвердил frontend
deploy и health; static release `6e4b82f76f63-20261001150934`.
Schema/runtime configuration/model selection не менялись.

В существующем owner-authenticated Staff браузере реальная `gl-1`-страница
перезагружена: новая кнопка «Generate using table types» доступна рядом с обычной
генерацией; прежний локальный результат восстановлен, старый ETag сохранил
правильную пометку stale. Изменения metadata в production не сохранялись и не
публиковались; новая OpenRouter-генерация при браузерной проверке не запускалась.
Смешанные типы и оба model-pass проверены изолированными тестами с SDK mock.
Снимок: `.runtime/vmshpwa/metadata-explicit-types-proof/tlf-success.jpg`.
Итог: 31 domain, 2 HTTP, 40 frontend tests PASS; types/lint/i18n/build PASS.
