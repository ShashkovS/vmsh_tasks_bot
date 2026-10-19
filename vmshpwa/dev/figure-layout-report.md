# Рисунки в материалах — реализация и проверка

## Инкремент 1 октября 2026

Реализован [принятый план](../docs/figure-layout.md): редактор на самом рисунке,
общий для условий, подсказок и решений. Левая кнопка задаёт rem-ширину и размещение,
правая переносит/скрывает рисунок и открывает дополнительные настройки. Старые
отдельные панели убраны. Маленькие изображения, включая узкие рисунки исходника,
сохраняют читаемый размер и получают кнопки под изображением. Открытие/закрытие
меню без изменения поля не создаёт override ширины.

Дополнение пользователя включено: «В тексте без обтекания» (`center-source`)
оставляет рисунок между исходными абзацами, центрирует и снимает float. Переход
из этого режима в конкретный пункт или раздел явно меняет размещение. Изменение
только ширины сохраняет исходное место. Повторы одного файла остаются независимыми.

Правки автоматически сохраняются в версионируемый черновик. После reload Staff
видит неопубликованное оформление и может опубликовать его без повторной загрузки/
review. До публикации Student/Family получают прежний снимок; после публикации
того же TeX меняется publicationId и обновляются web/офлайн-данные. Публикация
и планирование проверяют версию черновика внутри транзакции. История и rollback
поддерживают несколько снимков одной revision.

### Проверки текущего инкремента

| Gate                                   | Команда и результат                                                                                                                                                                                                                                                                      |
| -------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Domain / HTTP / repository / migration | `VMSH_RUNTIME_PROFILE=pwa-e2e NATS_SERVER= .venv/bin/python -m pytest -q pwa_tests/domain/test_figure_layout.py pwa_tests/integration/test_content_http_api.py pwa_tests/integration/test_content_repository.py pwa_tests/integration/test_figure_layout_migration.py` — **107 passed**. |
| Frontend unit                          | Из `vmshpwa`: `vitest run --project unit --maxWorkers=2 --testTimeout=20000` — **974 passed**, 192 файла. После финального уточнения маленьких исходных рисунков дополнительно проходят **21** проверка затронутых renderer/editor.                                                      |
| Storybook / axe                        | `vitest run --config vitest.storybook.config.ts apps/staff/src/figure-layout-editor.stories.tsx packages/content/src/math-document.stories.tsx` — **18 passed**: width/placement, save failure, tiny source, абсолютные размеры и mobile; без исключений accessibility.                  |
| Реальные браузеры                      | `make pwa-e2e-figure-layout` — **12 passed**, 2,6 минуты, Chromium, Firefox, WebKit; редактор, печать и PNG/ZIP в ru/en. Runner собирает все четыре приложения и использует изолированную БД/порты/media.                                                                                |
| Статические проверки                   | `make pwa-typecheck pwa-lint pwa-i18n-check`, отдельный tools TypeScript, scoped Prettier и Ruff — проходят. После изменения текста выполнен `make pwa-i18n-extract`.                                                                                                                    |
| Schema                                 | `python -m vmshpwa.scripts.schema_inventory check` — 498 product objects, fixtures/`docs/db_structure.sql` синхронизированы. Миграция 0106: up/down/up, frozen legacy scales и immutable trigger.                                                                                        |

Использован установленный pnpm 11.15.1 из локального package-manager-store:
системный bootstrap пытался обращаться к registry. Frontend unit ограничен двумя
workers из-за нагрузки машины; timeouts не изменены в конфигурации проекта.
Python выдаёт предупреждения сторонних библиотек; тесты проходят.

Ключевые доказательства:

- Публикация → width 12 rem → неизменность Student/Family → reload Staff и dirty
  flag → повторная публикация того же исходника → 192 px у школьника без reload.
- Все пять размещений, ширины 0,5/12/80 rem, обе границы листка, перенос в обе
  стороны с общим блоком, пункт, hide/restore и независимость повторного asset.
- Domain/HTTP проверяют разделы решений, исчезновение dirty при возврате,
  stale layout/publication 409, точный rollback по targetPublicationId и сохранение
  отложенной ширины 12 rem после последующей правки черновика до 80 rem.
- Старый figure-scale API тоже оставляет опубликованное содержимое неизменным.
- Offline unit заменяет содержимое при новом publicationId той же revision;
  общий replacement hook проверяется для Student/Family.
- Viewport 320/390/1280 px, обе темы и root font-size 200%; keyboard Enter/Escape
  и возврат фокуса. Storybook проверяет расположение кнопок под узким исходным
  рисунком и отсутствие изменения ширины при открытии меню.
- PNG экспорт: ZIP содержит две задачи шириной 1600 px, красный рисунок есть
  только во второй. Telegram projection сохраняет порядок/подписи/скрытие.

### Снимки и границы проверки

Выбранные снимки сохранены в `figure-layout-2026-10-01/`; анимации меню завершены
до съёмки. Это артефакты отчёта, golden snapshots не обновлялись.

- [Chromium desktop light](figure-layout-2026-10-01/chromium/editor-1280-light.png),
  [320 px dark](figure-layout-2026-10-01/chromium/editor-320-dark.png),
  [200%](figure-layout-2026-10-01/chromium/editor-200-percent.png).
- [WebKit 390 px light](figure-layout-2026-10-01/webkit/editor-390-light.png),
  [320 px dark](figure-layout-2026-10-01/webkit/editor-320-dark.png).
- [Firefox desktop dark](figure-layout-2026-10-01/firefox/editor-1280-dark.png),
  [390 px light](figure-layout-2026-10-01/firefox/editor-390-light.png).
- [Student до правок](figure-layout-2026-10-01/chromium/student-before.png),
  [после публикации](figure-layout-2026-10-01/chromium/student-print.png),
  [PNG ZIP](figure-layout-2026-10-01/chromium/figures.zip).

Полный набор captures всех браузеров находится в ignored `vmshpwa/test-results/`.
В мобильных кадрах при прокрутке видна закреплённая шапка приложения. WebKit
использует DPR 2. Физические устройства/касания не проверялись: pointer API и
доступная клавиатура проверены в браузерах. Family payload проверен HTTP, offline
обновление — unit; отдельный offline/Family E2E в этом gate не запускался.

Владелец разрешил production-выпуск на оба сервера 1 октября. Commit/integration
и rollout завершены: VMSh через webhook, TLF через SSH-скрипт. Миграция рисунков
перенумерована в 0106 после параллельного выпуска 0104.course_metadata_model.
Генерация PDF и редактор Markdown-картинок вне этой итерации.

## Подготовка production-выпуска — 1 октября 2026

Редактор объединён с выпущенными изменениями метаданных `e8c3edf4`;
feature commit — `6835cbe5`. Миграция перенумерована в
`0106.pwa_figure_presentation`, после 0105, сохраняя выпущенную
`0104.course_metadata_model`. Schema inventory перегенерирован для обеих
доработок: 498 product objects.

После объединения прошли **138** backend/schema/metadata проверок,
**107** seed и deploy-data guard проверок, **975** frontend unit и **12** E2E
в Chromium/Firefox/WebKit (3 минуты), typecheck/lint/i18n и четыре сборки.
Первый интеграционный E2E обнаружил устаревший digest baseline-v1 после
миграции метаданных. Отдельное сравнение canonical rows без нового
`courses.metadata_model` подтвердило прежний digest; изменён только
ожидаемый digest фикстуры, её прежние данные сохранены.

TLF использует адаптированный предыдущий SSH cutover:
[deploy_figure_layout.sh](../../docs/deploy/tlf-app/deploy_figure_layout.sh) и
[figure_layout_data_check.py](../../docs/deploy/tlf-app/figure_layout_data_check.py).
Скрипт принимает проверенный полный SHA, собирает отдельный frozen release,
репетирует миграцию на копии, сохраняет backup, останавливает PWA/Zoom/analytics
writers и сравнивает все прежние product columns. Новый frozen scale проверяется
отдельно. Runtime/credentials/NATS сохраняются. При ошибке откатываются только
0106/source/static, без замены БД; поздние правки рисунков блокируют этот откат.
[Регрессия проверки сохранности](../../pwa_tests/integration/test_tlf_figure_release_guard.py).

Перед переключением сохранены SHA256/MIME **182** прежних публичных JS/CSS
URL (по 91 на портал) для проверки сохранности открытых вкладок после выпуска.
Владелец разрешил push/autodeploy VMSh и SSH-выпуск TLF; rollout завершён.

## Production — 2026-10-01

На обоих порталах выпущен runtime source
`3bb202815078d89c55c9a819ee3584f66fc6d8a1` (feature `6835cbe5`).
VMSh обновлён штатным webhook после push в `vmshpwa`; TLF —
`sudo bash /tmp/tlf-figures-3bb202815078.sh <full SHA>` через `tlfprepagent`.
Оба выпуска завершились успешно около 13:21 UTC / 16:21 Asia/Nicosia.

| Портал | Активный static release                 | Backup до / после                                                                        |
| ------ | --------------------------------------- | ---------------------------------------------------------------------------------------- |
| VMSh   | `3bb202815078-20261001131914`           | `vmsh-before-deploy-20261001132024.sqlite3` / `vmsh-after-deploy-20261001132124.sqlite3` |
| TLF    | `tlfprep-20261001-figures-3bb202815078` | `20261001T132032.802773Z` / `20261001T132100.591519Z`                                    |

Миграция 0106 применена на обеих базах, всего **78** миграций. VMSh сохраняет
**23** исторических снимка с `layout_version=-1`; их frozen scales соответствуют
старым scale overlays. На TLF исторических снимков этого типа нет. Immutable
trigger присутствует в обеих базах; backup integrity — `ok`.

TLF rehearsal и cutover сравнили все **154** прежние product tables/columns:
контрольные суммы совпали, credentials не изменились, сохранены три raw Zoom
receipts. VMSh before/after backup сохраняют содержимое **151** из 154 таблиц;
изменились только `auth_events`, `auth_refresh_consumed_secrets`, `auth_sessions`
при возобновлении авторизованных запросов после запуска. Предметные данные,
публикации, draft layouts и старые масштабы совпадают. Проверка читала завершённые
backup с `immutable=1`, без создания WAL/shm в каталоге backup.

На каждом публичном портале прошли **25 read-only HTTP checks**. Все четыре
`build-provenance.json` соответствуют новым release ID, production profile,
MSW/prototype=false и прежним media origins. Новые публичные Staff bundles
содержат `center-source` и `widthRem`. Все **182** прежних JS/CSS URL (91 на портал)
возвращают HTTP 200 с прежними SHA256 и MIME: открытые вкладки сохраняют chunks.

PWA и legacy Telegram на VMSh, PWA и Zoom на TLF активны. NATS не перезапускался:
VMSh PID `3018`, TLF PID `1936264` сохранены. Runtime/nginx/systemd конфигурации
не менялись; сообщение VMSh deploy про инфраструктуру относится к добавленному
TLF cutover script в git, переустановка webhook не требуется.

Полный retained TLF record:
`/web/vmsh_tasks_bot/deploy/releases/tlfprep-20261001-figures-3bb202815078/`:
rehearsal, before/after digests, backup, health и `http-smoke.log`.
[Операционный runbook](../../docs/deploy/tlf-app/README.md#inline-figure-editor--2026-10-01).
Live-проверки были публичными/read-only; сценарий редактирования и публикации
в авторизованном production Staff не повторялся. Он проверен до выпуска на
изолированном E2E в трёх браузерах. Synthetic submissions/Zoom events или
сообщения реальным адресатам для проверки не создавались.

## Исторический отчёт 15 сентября 2026

Реализован [контракт](../docs/figure-layout.md), с исключённой пользователем
генерацией PDF. Изменения находятся в рабочей копии; commit/push и production
не выполнялись. Прежние публикации автоматически не переобрабатываются.

## Что исправлено

Вынесенные рисунки сохраняются в подсказках/решениях без переноса текста условия.
Ответы и объяснения отбираются по отдельному пункту. Несогласованная разметка
выдаёт ошибку обработки. Редактор использует идентификатор вхождения: два использования
одного файла можно перемещать и скрывать независимо, сохраняя подпись и масштаб.

Расположение сохраняется в черновик с проверкой версии. Публикация фиксирует
неизменяемый документ и Telegram-производную атомарно. Откат и отложенная активация
используют соответствующий снимок, а не свежий черновик. Повторная обработка READY
исходника обновляет производные, сохраняя ручное расположение и прежнюю публикацию.

В Staff инструменты находятся вне ученической композиции. После обновления превью
сохраняется признак проверенных метаданных и доступна кнопка публикации. Для старого
формата без идентификаторов предлагается «Повторно обработать исходник». Если
нужных файлов нет на сервере, API явно просит загрузить исходник с рисунками заново.

PWA, печать и PNG читают снимок. Telegram-превью и `send_published` строятся из той же
композиции; разрешение защищённых assetId в публичные HTTPS URL проверено тестовым
транспортом. Реальным адресатам сообщения не отправлялись. Telegram использует
нативное оформление вместо web CSS для размеров и обтекания. PDF исходника остаётся
доступен с пояснением, что редактор расположения его не меняет.

## Регрессионные исходники

Файлы владельца сохранены без изменения кодировки в
`pwa_tests/fixtures/figure-layout/`. Проверки: `pwa_tests/domain/test_figure_layout.py`.

| Пример              | До исправления              | После                            |
| ------------------- | --------------------------- | -------------------------------- |
| 1н.9                | Только «см. рисунки»        | Сохранены оба вынесенных рисунка |
| 1н.11, шахматы      | Пропущен вынесенный рисунок | Рисунок присутствует             |
| 1н.12, лабиринт     | Пропущен вынесенный рисунок | Рисунок присутствует             |
| 1п.1а               | Ответы обоих пунктов        | 48 треугольников и свой материал |
| 1п.1б               | Ответы обоих пунктов        | 243 треугольника и свой материал |
| Повтор одного файла | Нельзя различить по assetId | Два независимых occurrenceId     |

## Проверки

- 178 backend-тестов: compiler, figure layout, Telegram publisher, HTTP, repository,
  миграция; 3 предупреждения стороннего SymPy. Полный запуск с `pytest -n 3`.
- Дополнены проверки CSRF и существующих прав управления материалами, конфликта
  PUT, повторной обработки, stale результата компиляции, атомарного отказа,
  неизменности опубликованного содержимого, rollback и scheduled snapshot.
- Миграция 0093: up/down/up, внешние ключи и сохранение старых публикаций.
- Staff и tools TypeScript, целевой ESLint, Ruff, unit-тест редактора проходят.
  У `content-page.tsx` остаются три ранее существовавших замечания ESLint вне этой
  доработки; другие файлы проверены без исключений.
- Браузерный gate: `make pwa-e2e-figure-layout` — **9 passed**, 47,8 секунды,
  без повторов. Chromium, Firefox и WebKit; editor, whiteboard export, worksheet print.
- Тест отмены PNG стабилизирован: реальные запросы рисунков удерживаются до нажатия
  «Отмена». Это исключает ситуацию, когда маленький архив успевал скачаться раньше
  тестового клика. Продуктовый код экспорта не изменялся.

## Браузерные артефакты

Изолированный backend, реальные API и загрузка SVG; без production-данных.
Два вхождения одного SVG: перенос к пункту, скрытие, reload, перенос к другой задаче,
порядок, восстановление клавиатурой, скрытие и явная публикация. До публикации
ученический JSON неизменен. После публикации в первой PNG нет красных пикселей
рисунка, во второй они есть; ширина обеих PNG 1600 px. ZIP содержит ровно две задачи.

Desktop 1280, мобильные 320/390 px, обе темы. Снимки и скачанные файлы сохранены
в `figure-layout-artifacts/`; это новые отчётные снимки, не замена golden snapshots.

Пользовательская приёмка и выпуск ещё не выполнялись. Чтобы исправить загруженные
листки: повторная обработка → просмотр/расположение → явная публикация.

### Примеры

- [ZIP Chromium](figure-layout-artifacts/chromium/figures.zip)
- [До правок](figure-layout-artifacts/chromium/student-before.png) и
  [после публикации](figure-layout-artifacts/chromium/student-print.png)
- [Desktop, светлая тема](figure-layout-artifacts/chromium/editor-1280-light.png)
- [320 px, тёмная тема](figure-layout-artifacts/chromium/editor-320-dark.png)
- [Первая задача без скрытого рисунка](figure-layout-artifacts/chromium/math-5-7_901н.01.png)
- [Вторая задача с сохранённым вхождением](figure-layout-artifacts/chromium/math-5-7_901н.02.png)

Артефакты WebKit и Firefox находятся в соседних каталогах с теми же именами
снимков; номера занятий 902/903. Мобильные снимки элемента включают наложение
закреплённой шапки приложения при прокрутке; содержимое и кнопки не обрезаны.
