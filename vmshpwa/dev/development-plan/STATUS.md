# Статус плана разработки

## Правка названия созданного занятия — готово к owner-проверке, 7 сентября 2026

- Staff-страница существующего занятия получает отдельную карточку «Название
  занятия»: можно задать, исправить или очистить название. Правка меняет
  общее course-level название для этого номера во всех группах курса, не
  затрагивая расписание и публикации. Сервер защищает запись ETag-версией;
  реализация: [`content_routes.py`](../../../apps/pwa_api/content_routes.py),
  [`content.py`](../../../db_methods/pwa/content.py),
  [`content-page.tsx`](../../apps/staff/src/content-page.tsx).

## Family: занятие без названия — готово к owner-проверке, 7 сентября 2026

- Read-model Family теперь принимает корректное серверное `title: null` для
  опубликованного занятия без собственного названия. В карточке и при открытии
  листка показывается `Занятие N`, а не `null`; успешный ответ больше не
  превращается в ошибку загрузки. Реализация и regression:
  [`family-courses.ts`](../../packages/contracts/src/family-courses.ts),
  [`family-children-page.tsx`](../../apps/family/src/family-children-page.tsx),
  [`content-page.tsx`](../../apps/family/src/content-page.tsx).

## Фотографирование решения из Student — готово к owner-проверке, 2 сентября 2026

- В форме письменного решения отдельная кнопка с камерой открывает системную
  камеру устройства (предпочтительно заднюю) через `capture="environment"`.
  Обычная кнопка добавления фотографии осталась отдельной: она открывает
  файловый выбор/галерею и по-прежнему позволяет выбрать несколько файлов.
  Обе операции используют один и тот же безопасный клиентский pipeline сжатия
  и сохранения черновика: [`student-written-submission.tsx`](../../apps/student/src/student-written-submission.tsx),
  [`chat-composer.tsx`](../../packages/product/src/chat-composer.tsx).

## Чистый старт и мягкое удаление школьника — готово к owner-проверке, 25 августа 2026

- Telegram-бот больше не наполняет чистую БД старым Google-sheet при запуске:
  импорт остаётся явной legacy-операцией. В Staff добавляется мягкое удаление
  школьника: legacy user переводится в `DELETED`, web-вход выключается, сессии
  завершаются, а исторические записи не удаляются. Реализация:
  [`tg_bot.py`](../../../apps/tg_bot.py),
  [`admin_account_routes.py`](../../../apps/pwa_api/admin_account_routes.py),
  [`staff-student-directory-page.tsx`](../../apps/staff/src/staff-student-directory-page.tsx).
- Проверки: Staff account/enrollment HTTP **17 PASS**, contracts/app-shell/Staff
  typecheck и admin-client Vitest **17 PASS**, Ruff, Prettier и `git diff --check` — PASS.

## Group announcements deliver to devices — готово к owner-проверке, 25 августа 2026

- Staff «Рассылки» больше не являются только баннерами на «Сейчас»: active
  announcement создаёт account-scoped `group_announcement` событие в момент
  `startsAt`. Поэтому оно видно в списке уведомлений и попадает в существующий
  Web Push outbox на каждое разрешённое устройство Student/Family. Будущая
  правка заменяет ожидающее событие; отмена его удаляет, а правка уже начатого
  объявления не дублирует доставку. Реализация:
  [`group_banner_notifications.py`](../../../models/pwa/group_banner_notifications.py),
  [`group_banner_routes.py`](../../../apps/pwa_api/group_banner_routes.py),
  [`push_delivery.py`](../../../helpers/pwa/push_delivery.py).
- В Staff checkbox явно объяснён: скрытие — localStorage текущего браузера
  получателя, не отмена рассылки. Контракты и Student/Family settings дают
  отдельную категорию «Объявления группы»:
  [`notifications.ts`](../../packages/contracts/src/notifications.ts),
  [`student-notifications-page.tsx`](../../apps/student/src/student-notifications-page.tsx),
  [`family-notifications-page.tsx`](../../apps/family/src/family-notifications-page.tsx).
- Проверки: group banner repository/HTTP + Web Push **17 PASS**; строгий
  TypeScript Staff/Student/Family/contracts — PASS.

## Светлая тема по умолчанию — готово, 23 августа 2026

- Общий `AppProviders` больше не наследует тёмную тему от системного
  `prefers-color-scheme`: первый вход в Student, Family или Staff всегда
  светлый. Явный выбор пользователя по-прежнему изолированно сохраняется в
  `localStorage` и позволяет переключиться на тёмную тему:
  [`providers.tsx`](../../packages/app-shell/src/providers.tsx).
- Regression в
  [`runtime-bootstrap.test.tsx`](../../packages/app-shell/src/runtime-bootstrap.test.tsx)
  фиксирует светлый первый вход даже при системной тёмной теме.
- Проверки: focused Vitest **10 PASS**, strict TypeScript, ESLint, полный
  `make pwa-build` и `git diff --check` — PASS.

## Компактные persistent ID — финальный полный gate в работе, 23 августа 2026

- Владелец утвердил замену случайных PWA record ID на компактные
  детерминированные формы: `u-127`, `c-912`, `g-627`, `gl-13`, `cr-1`.
  Persistent tables сохраняют только `INTEGER PRIMARY KEY`; compatibility
  projection `public_id` будет virtual, без stored text и unique index.
  Реестр префиксов и намеренно сохранённые secret/idempotency identifiers:
  [`compact-identifiers.md`](../../docs/compact-identifiers.md).
- PWA migrations и creation paths используют virtual `public_id`, получаемый
  после insert через `RETURNING`; stored UUID-колонки и их text-FK удалены.
  Written submissions/reviews/support, classroom delivery/import/layout/plan и
  news mirror/moderation вместе с их fixtures переведены на реальные компактные
  значения. В `news_posts` и classroom snapshot-снимках больше нет дублей
  текстовых public ID; связи используют integer FK. Review/classroom/news
  Playwright seed-ы используют фиксированные integer rowid и соответственно
  `wq-9701`/`p-9701`, `ipe-9801`/`gl-9801`, `news-9601`; старые semantic UUID-like
  ID не сохраняются. Оставшиеся Family и oral Playwright seed-ы переведены на
  фиксированные integer `rowid`; их public формы теперь получаются virtual как
  `u-10404`, `a-10201`, `en-10601`, `gl-921`, `ow-921`.
- Проверены: written submissions **55 PASS** и legacy attempt schema **3 PASS**;
  review repository **34 PASS** (один process-pool тест не запускается в sandbox
  из-за системных semaphores), review migration/notification fixtures **13 PASS**
  и review HTTP **10 PASS**; Phase-7 classroom fixtures **21 PASS**, classroom
  HTTP **5 PASS**; Phase-8 news **18 PASS**. `make pwa-schema-update
pwa-schema-check` и PWA TypeScript typecheck — PASS, product SHA `8076aeb3…`.
- Существующая SQLite БД намеренно не поддерживается: владелец создаст чистую
  БД.

Последнее обновление: 2026-08-23. Изолированный content E2E после зачистки
fixture seed-ов — **6 PASS** (Chromium, WebKit, Firefox). Полный PWA E2E
перезапускается на чистой БД; затем будут повторены все backend и frontend
тестовые ворота.

## Cyrillic TikZ standalone compatibility — готово к owner-проверке, 22 августа 2026

- Исходный Windows-1251 TeX декодируется до extraction как прежде; ошибка `Invalid UTF-8 byte "BF` возникала уже в server-generated UTF-8 `content.tex` на Cyrillic control sequence `\пункт`. TikZ extractor заменяет legacy command только в производном source на ASCII `\vmshPartLabel`, а standalone preamble явно задаёт UTF-8, T2A и Russian babel. Uploaded source не меняется: [`tikz.py`](../../../helpers/pwa/content/tikz.py), [`assets.py`](../../../helpers/pwa/content/assets.py).
- Parser/TikZ regression **93 PASS**. Реальный production smoke с фрагментом пользовательского source требует явного разрешения на передачу приватного фрагмента на сервер.

## TikZ conversion diagnostics — готово к owner-проверке, 22 августа 2026

- Если `pdflatex` или `pdf2svg` завершается ошибкой, Staff получает этап конвертации, точный сгенерированный standalone `content.tex` и bounded output инструмента; временный server path redacted. Эти данные видны в раскрытом блоке под ошибкой, а не теряются в journal. Реализация: [`assets.py`](../../../helpers/pwa/content/assets.py), [`content_routes.py`](../../../apps/pwa_api/content_routes.py), [`content-page.tsx`](../../apps/staff/src/content-page.tsx).
- Focused converter/API regression **2 PASS**, Staff typecheck — PASS.

## TikZ preparation before compile — готово к owner-проверке, 22 августа 2026

- TikZ больше не получает ложную parser-ошибку о «переданной библиотеке assets»: это исходный блок, а не файл, который должен приложить Staff. Перед каждым compile Staff явно запускает server-side preparation, перечитывает revision с fresh ETag и только затем собирает материал. Если converter действительно не справился, отображается его конкретная причина и capability, а не несуществующий SVG. Старые revision с legacy `asset.missing` теперь также направляются в этот recovery path: [`parser.py`](../../../helpers/pwa/content/parser.py), [`content-page.tsx`](../../apps/staff/src/content-page.tsx).
- Regression: content compiler **84 PASS**, Staff typecheck — PASS.

## Массовая загрузка скрыта — 22 августа 2026

- Блок массовой загрузки больше не показывается в Staff-карточке занятия: пока его UX перерабатывается, единственный видимый путь загрузки — отдельные карточки условия, подсказки и решения. Компонент и API намеренно сохранены, чтобы вернуться к функции без восстановления backend-контракта: [`content-page.tsx`](../../apps/staff/src/content-page.tsx), [`bulk-content-upload.tsx`](../../apps/staff/src/bulk-content-upload.tsx).

## Content compile conflict recovery — готово к owner-проверке, 21 августа 2026

- Двойной быстрый клик больше не запускает вторую upload/compile цепочку до React render: синхронный guard в [`content-page.tsx`](../../apps/staff/src/content-page.tsx) удерживает ровно один запрос. Это исключает ложный `409 content_conflict` после того, как первый запрос уже сохранил terminal invalid revision.
- Если конфликт всё же пришёл из второй вкладки или сети, Staff читает сохранённую revision: `invalid` показывает её настоящие diagnostics, `ready` открывает preview. Общее «Материал уже изменён» остаётся только когда durable outcome получить нельзя.

## TikZ progress and conversion diagnostics — готово к owner-проверке, 21 августа 2026

- При upload файла с `tikzpicture` Staff сразу сообщает «Готовим рисунки из TikZ», затем переключается на проверку структуры. В asset recovery каждый TikZ-слот показывает «Конвертируем TikZ», а успешное завершение автоматически продолжает сборку.
- Ошибка conversion теперь сообщает конкретный logical TikZ asset, недоступный server capability либо безопасную redacted detail конвертера вместо внутреннего «SVG отсутствует в библиотеке assets». Реализация: [`content-page.tsx`](../../apps/staff/src/content-page.tsx), [`revision-assets-recovery.tsx`](../../apps/staff/src/revision-assets-recovery.tsx), [`staff-publishing.tsx`](../../packages/product/src/staff-publishing.tsx). Product/Staff typecheck и focused Staff Vitest — PASS.

## Upload retry and fresh ETag recovery — готово к owner-проверке, 22 августа 2026

- Выбор файла фиксируется в UI синхронно — без ожидания чтения cloud-backed File; его byte snapshot создаётся непосредственно перед upload. Поэтому первый выбор файла виден сразу, а повторный выбор того же файла корректно вызывает `change`.
- «Найти недостающие рисунки» при `version_conflict` читает revision и ровно один раз повторяет compile с fresh ETag, а не оставляет экран неподвижным. Для terminal invalid revision кнопка `LatexUpload` называется «Обновить статус» и показывает durable diagnostics; uploaded revision продолжает настоящую повторную сборку. [`content-page.tsx`](../../apps/staff/src/content-page.tsx), [`staff-publishing.tsx`](../../packages/product/src/staff-publishing.tsx). Product/Staff typecheck и focused Vitest — PASS.

## AI-перегенерация metadata — готово к owner-проверке, 25 августа 2026

- После automatic/manual matching Staff может запросить «Сгенерировать metadata» для любой revision condition. Для повторной версии либо уже сохранённой таблицы интерфейс спрашивает подтверждение, а API не выполнит расходующий модель запрос без `confirmedOverwrite`. Ответ OpenRouter полностью заменяет только локальный черновик; публикации и server mutation до кнопки «Сохранить metadata» нет.
- В workflow показан явный результат генерации: successful response подтверждает замену черновика, а ошибка OpenRouter/API остаётся рядом с кнопкой, а не исчезает вместе с progress loader.
- Контракт генератора отделяет допустимый формат от правильного ответа: `Выбор` содержит полный закрытый список вариантов, включая неверные. Source-aware нормализация также распознаёт вопрос «У кого…» по паре имён в условии и не даёт свести его к `Строка`/regex по одному верному ответу.
- Серверный адаптер использует официальный async `openrouter` SDK, strict Pydantic JSON Schema, `reasoning_effort="low"` и non-streaming call. Длинный TeX размещён в начале user-prompt, а canonical identities/`problemId` возвращаются и проверяются сервером; лишние или пропущенные model rows отклоняются.
- Ключ читает только `OPENROUTER_API_KEY` из profile JSON в `Config.openrouter_api_key`, не из environment и не из PWA runtime payload. Full content HTTP + domain generation **51 PASS**, TypeScript contracts/content/Staff и Staff workflow Vitest — PASS; один настоящий structured-output smoke с коротким условием успешно вернул тестовую metadata.

## Исправление опубликованных метаданных — готово к owner-проверке, 21 августа 2026

- Staff может вернуться к составу задач либо к таблице metadata уже опубликованного condition. Лишняя задача исключается из актуального листка, пропущенная добавляется, а исправленный тип/ответ становится единственной истиной для Student/Family.
- `0082.pwa_published_metadata_corrections.sql` заменяет append-only review current-state версией с отдельным optimistic ETag. Прежние submissions и результаты остаются артефактами, но исключённые задачи не попадают в актуальные выборки.
- Перепроверка расширена с `pending_configuration` до всех сохранённых ответов текущей тестовой задачи. Regression доказывает: опубликованный правильный ответ `179` после правки ключа на `180` становится неверным. Проверки: full content HTTP **47 PASS**, schema inventory **21 PASS**, content compiler **84 PASS**, Staff/product TypeScript и workflow Vitest — PASS.

## Pilot content upload diagnostics and next-task preambles — 21 августа 2026

- Новый condition parser переносит разделы, пояснения и рисунки между двумя задачами в начало следующей задачи; завершающий блок последней задачи не теряется. Это закреплено в [`web_document.py`](../../../helpers/pwa/content/web_document.py) и regression [`test_content_compiler.py`](../../../pwa_tests/domain/test_content_compiler.py).
- Массовая загрузка теперь оставляет у проблемной строки server diagnostics с line/column, recovery и missing-asset names, а кнопка «Открыть исправление» ведёт в сохранённую revision. Реализация: [`bulk-content-upload.tsx`](../../apps/staff/src/bulk-content-upload.tsx) и [`bulk-content-upload-model.ts`](../../apps/staff/src/bulk-content-upload-model.ts).
- Проверки: content compiler **84 PASS**, Staff bulk-upload Vitest **10 PASS**, contracts и Staff TypeScript — PASS; `git diff --check` — PASS. Existing published materials deliberately were not changed.

## Rich Markdown для новостей и объявлений — готово к review, 21 августа 2026

- В ветке `vmshpwa` реализован сквозной RichDocument v1 для local news и group banners: строгий `@puregram/rich` parser, нормализованный AST, safe React renderer, lazy CodeMirror 6 authoring surface, server-side media copy и v1 wire compatibility. Решение и границы: [`12-phase-8-news-and-notifications.md`](12-phase-8-news-and-notifications.md); runtime contract: [`packages/contracts/src/rich-document.ts`](../../packages/contracts/src/rich-document.ts).
- v2 API и persistence находятся в [`news_moderation_routes.py`](../../../apps/pwa_api/news_moderation_routes.py), [`group_banner_routes.py`](../../../apps/pwa_api/group_banner_routes.py), [`0081.pwa_rich_markdown.sql`](../../../migrations/0081.pwa_rich_markdown.sql) и [`models/pwa/rich_document.py`](../../../models/pwa/rich_document.py). Student/Family renderer и Staff authoring связывают [`rich-document.tsx`](../../packages/product/src/rich-document.tsx), [`rich-markdown-editor.tsx`](../../apps/staff/src/rich-markdown-editor.tsx), news и broadcasts pages.
- Создание local news — полноширинная секция над списком новостей, как в [`staff-group-banners-page.tsx`](../../apps/staff/src/staff-group-banners-page.tsx), а не модальное окно: [`staff-news-page.tsx`](../../apps/staff/src/staff-news-page.tsx). Пустой Markdown нейтрален; при временной ошибке редактор удерживает последний валидный preview 2 секунды, после чего показывает короткую подсказку. Это закреплено в [`rich-markdown-editor.test.tsx`](../../apps/staff/src/rich-markdown-editor.test.tsx) и news E2E.
- Gates: focused Python **23 passed**, Vitest **14 passed**, strict contracts/product/Staff typecheck, targeted Prettier/ESLint/Ruff, `make pwa-build` и isolated `make pwa-e2e-news` — PASS. После inline-полировки composer добавлен focused editor test; повторный `make pwa-e2e-news` в текущем agent runtime блокируется до Playwright из-за недоступного NATS (`NoServersError`). Следующий owner gate — visual/a11y review; массовые рассылки и Telegram delivery остаются вне scope.

## Student/Family worksheet typography bundle — 20 August 2026

- Student и Family теперь явно подключают общий production CSS математических
  материалов после базовых UI-стилей. До исправления Student bundle не содержал
  `.vmsh-math-content`, поэтому опубликованный листок рендерился системным
  IBM Plex Sans вместо Computer Modern и игнорировал размеры, интервалы,
  переносы и раскладку рисунков из Staff preview.
- Полезная ширина текста остаётся `90ch`; внешняя «бумага» ограничена `96ch`,
  чтобы сохранить внутренние поля. Кнопки статуса, вопросов, подсказки и решения
  собраны в компактную строку и не разрывают условие большими блоками.
- Исправление не меняет content API или сохранённые документы: Student, Family
  и Staff используют один и тот же `@vmsh/content/styles.css`.
- Evidence: [`student/main.tsx`](../../apps/student/src/main.tsx),
  [`family/main.tsx`](../../apps/family/src/main.tsx),
  [`student-task-detail-page.tsx`](../../apps/student/src/student-task-detail-page.tsx)
  и [`content.css`](../../packages/content/src/content.css).
- Проверки: lint, 650 unit tests, targeted TypeScript и production builds
  Student/Family — PASS;
  собранные CSS обоих приложений содержат Computer Modern,
  `.vmsh-math-body` и `max-inline-size:90ch`; `git diff --check` — PASS.

## Recoverable PWA update activation — 18 August 2026

- Автоматическая попытка применить новую версию больше не блокирует навсегда
  кнопку «Обновить сейчас», если service worker ещё не успел перехватить
  страницу. Защита действует только во время одного активного вызова; после его
  завершения обновление можно повторить вручную или в следующий безопасный
  момент.
- Ошибка низкоуровневой активации также освобождает повторную попытку. Реальная
  перезагрузка по-прежнему выполняется только после `controllerchange`, поэтому
  незавершённая отправка или ввод пользователя не теряются.
- Исправление одинаково применено к Student и Family. Регрессионный тест
  воспроизводит обе причины: зависшую автоматическую активацию и исключение
  updater перед последующим нажатием кнопки.
- Evidence: [`student/src/pwa-update.tsx`](../../apps/student/src/pwa-update.tsx),
  [`family/src/pwa-update.tsx`](../../apps/family/src/pwa-update.tsx) и
  [`pwa-update.test.tsx`](../../apps/student/src/pwa-update.test.tsx).
- Проверки: frontend unit **650/650**, ESLint, targeted TypeScript и production
  builds Student/Family — PASS. Runtime-isolation E2E не стартовал из-за
  недоступного локального NATS; браузерная часть сценария не выполнялась.

## Working classroom event and allocation flow — 18 August 2026

- `/staff/classrooms` больше не зависит от Storybook fixture: admin создаёт и
  редактирует реальное очное событие, его московские дату/время и участвующие
  групповые занятия. Новые события имеют читаемые public IDs вида
  `in-person-YYYY-MM-DD`.
- К событию подключены существующие реальные catalog/layout/assignment API:
  наследование последнего подтверждённого плана, компактная статистика комнат,
  localStorage-черновик, single/bulk select, пересчёт и подтверждение snapshot.
- «Разослать аудитории» остаётся отдельным явным действием с preview каналов
  PWA/личный Telegram. Family только читает актуальное назначение; автоматической
  рассылки после правки нет.
- Student и Family показывают дату/время объявленного события и номер аудитории
  только из подтверждённого плана.
- Evidence: [`classroom-event-page.tsx`](../../apps/staff/src/classroom-event-page.tsx),
  [`classroom_layout_routes.py`](../../../apps/pwa_api/classroom_layout_routes.py),
  [`classroom-planning.tsx`](../../packages/product/src/classroom-planning.tsx),
  [`classroom-catalog.spec.ts`](../../e2e/classroom-catalog.spec.ts) и
  [`classroom-and-oral-workflow.md`](../../docs/classroom-and-oral-workflow.md).
- Проверки: HTTP integration **5/5**, frontend unit **648/648**, classroom E2E
  **9/9** в Chromium/WebKit/Firefox, lint/typecheck/build — PASS. В полном Python
  gate **1763 passed / 6 skipped**; 2 теста golden corpus падают из-за локального
  owner corpus drift и не связаны с classroom increment. Snapshots не менялись.

## Staff lesson upload deadlock recovery — 18 August 2026

- `/staff/lessons` запрашивает полный доступный каталог занятий, поэтому
  сохранённые черновики, прошлые и будущие занятия больше не скрываются за
  проекцией «одно текущее занятие на группу» рабочей сводки.
- После частичного создания занятия Staff переходит в первое реально созданное
  групповое занятие. Повторно создавать уже сохранённое занятие не требуется.
- Ошибка автоматической обработки TikZ возвращает сохранённые `revisionId`,
  `groupLessonId`, имя файла, рисунок и безопасную причину. Массовая загрузка
  показывает эти детали и рабочую кнопку «Открыть занятие» даже при ошибке,
  возникшей после сохранения revision.
- Рисунки из скрытых ответов/решений больше не блокируют загрузку условия;
  standalone TikZ поддерживает используемую в архивных листках команду
  `\пункт`.
- Проверки: Python domain/focused integration — PASS; полный затронутый HTTP
  suite **49 passed**; Staff Vitest **12 passed**; Ruff, Prettier, ESLint и
  targeted TypeScript — PASS; `git diff --check` — PASS.

## Shared file input affordance — 13 August 2026

- Общий native `Input type=file` получил явно выделенную primary-кнопку выбора,
  density-aware размеры и различимые hover/focus/disabled/invalid состояния.
- Изменение автоматически применяется к массовой и одиночной LaTeX-загрузке,
  XLSX-импорту задач и загрузке missing assets. Native picker, multiple,
  drag/drop и клавиатурная семантика сохранены; hidden Student photo picker не
  затронут.
- Story/interaction proof: `UI/Controls--file-inputs`.

## Historical TikZ static corpus gate — 13 August 2026

- Обе owner-local архивные иерархии рекурсивно проверяются по точным маскам
  `usl-??-?.tex`/`usl-??-?-sol.tex`; comments, macro bodies и document tail не
  считаются самостоятельными картинками.
- Production parser теперь использует один effective TikZ source с
  `% addToTikz`, dependency-scoped macros/colors/styles/libraries и positional
  wrapper; inline `\tikz`, несколько environments в wrapper, таблицы с
  `resizebox` и незакрытый print-only `center` покрыты regression tests.
- Статический прогон не компилирует TikZ и не изменяет S3/БД. Полные числа,
  позиции и три открытых source/toolchain blockers:
  [`phase2-content-tikz-corpus-2026-08-13.md`](../../../pwa_tests/reports/phase2-content-tikz-corpus-2026-08-13.md).

## Production content upload recovery — 13 August 2026

- Создание занятия в Staff теперь одним действием создаёт одноимённые занятия
  для всех активных групп выбранного курса; частичный результат не скрывается.
- Массовая загрузка по умолчанию выбирает «Условие». Для сохранённой revision с
  отсутствующими рисунками строка ведёт прямо к нужной карточке материала и
  объясняет последовательность TikZ SVG/upload → повторная сборка.
- Устранён production-сбой после успешной сборки SVG: клиент безопасно принимает
  известную форму weak ETag от nginx и восстанавливает opaque strong `If-Match`
  version-token. Brotli остаётся включённым для скорости больших API-ответов.
- Вместо текстовой ссылки прикреплённые raster/SVG показываются компактным
  превью оригинала; клик открывает увеличенный оригинал в Dialog без отдельной
  thumbnail-копии или нового backend endpoint.
- Proof, проверки и известные unrelated baseline failures:
  [`phase2-production-upload-recovery-2026-08-13.md`](../../../pwa_tests/reports/phase2-production-upload-recovery-2026-08-13.md).

## Lightweight production deploy — 11 August 2026

- Webhook deploy больше не запускает Python/TypeScript tests, lint, typecheck,
  Storybook, Playwright, visual regression, release re-verification,
  toolchain preflight или общий production HTTP smoke на двухъядерном сервере.
- На сервере остаются только необходимые install/build/package/migration шаги,
  SQLite backup/integrity guard и дешёвые systemd/runtime health checks.
- Актуальная политика и устанавливаемый скрипт:
  [`vmsh-webhook-setup.md`](../../../docs/deploy/vmsh-webhook-setup.md) и
  [`deploy-vmsh-tasks-bot.sh`](../../../docs/deploy/deploy-vmsh-tasks-bot.sh).

## Production Prometheus checkpoint — 11 August 2026

- В общий aiohttp app factory добавлен внешний bounded-cardinality middleware
  и loopback-only `GET /metrics`; route label берётся только из canonical
  aiohttp resource metadata, неизвестные маршруты получают `unmatched`.
- Gunicorn сохраняет существующий Unix socket для Nginx и теми же двумя
  workers дополнительно слушает `127.0.0.1:8000` для Prometheus. Systemd
  создаёт/очищает `/run/vmsh-prometheus`, а `child_exit` помечает worker dead.
- WebSocket lifetime исключён из HTTP latency и учитывается отдельным livesum
  gauge; idempotent lease не позволяет одному соединению уменьшить gauge дважды.
- Публичный `/metrics` закрыт exact Nginx location с `404`; ручной deploy после
  успешного старта создаёт file-discovery target `aiohttp.json`.
- Production unit теперь содержит готовые пути `vmshbeget` без `@@...@@` и
  устанавливается прямым копированием, без цепочки `sed`.
- Proof и известные unrelated baseline failures:
  [`production-prometheus-instrumentation-2026-08-11.md`](../../../pwa_tests/reports/production-prometheus-instrumentation-2026-08-11.md).

## Deploy-first учебный цикл — 10 August 2026

- Исправлен реальный импорт Family: `relationshipLabel = null` является
  допустимым значением и больше не ломает `/staff/users`; Staff показывает
  нейтральную подпись «родитель».
- На вкладке преподавателей добавлена атомарная пакетная загрузка из пяти
  TSV-столбцов с одним общим набором course/group scopes. Черновик хранится в
  `localStorage`, пароли не попадают в preview/response, а конфликт одной строки
  откатывает всю пачку. Реализация: [`teacher-batch-panel.tsx`](../../apps/staff/src/teacher-batch-panel.tsx),
  [`staff_access_routes.py`](../../../apps/pwa_api/staff_access_routes.py) и
  deploy-first E2E в [`authentication.spec.ts`](../../e2e/authentication.spec.ts).
- Добавлена пошаговая ручная приёмка на пустой production-подобной базе:
  [`manual-pilot-cycle.md`](../../docs/manual-pilot-cycle.md). Она проводит
  администратора через импорт школьников, создание преподавателя, занятие 0,
  публикации, Student submissions, Staff review, баннеры и семейный итог;
  аудитории из прохода исключены.
- Production-build Playwright теперь отдельно доказывает создание занятия из
  Staff UI, изменение расписания фаз и дедлайна, публикацию condition/solution,
  досрочное закрытие приёма и раскрытие решения Student. Сценарий находится в
  [`content-publication.spec.ts`](../../e2e/content-publication.spec.ts).
- Проверки текущего прохода: auth **90 passed / 12 intentional shared-DB skips**
  во всех трёх браузерах; отдельные deploy-first Student TSV/enrollment и
  Teacher create/scope/login/batch **3/3** в Chromium; content **6/6**, submissions
  **9/9**, review **3/3**, news/notifications **18/18** в Chromium, WebKit и
  Firefox.
- Зафиксирована честная граница: текущие `/staff/broadcasts` — PWA-баннеры, а
  явный итог занятия адресован Family. Student получает verdict сразу после
  review. Общая финальная Student/Telegram-рассылка пока не реализована и не
  изображается готовой.

## Public landing checkpoint — 10 August 2026

- Добавлен лёгкий React/Vite app [`apps/landing`](../../apps/landing) без API,
  авторизации, Telegram, Google и PWA-состояния. Root gateway и production
  release обслуживают его на `/`; пользователю показаны только Student и Family.
- Storybook proof: `Product/Landing--home` (mobile-light и desktop-light,
  interaction/a11y-проверка ссылок). Story связана с implementation map.
- Release/nginx proof: landing добавлен в provenance, static release, E2E gateway
  и production HTTP smoke; каталоги и файлы release получают публичные права
  `0755/0644`, чтобы nginx мог читать их после атомарной публикации.
- Проверки этого инкремента: lint, typecheck, Storybook browser tests **265/265**,
  Python gateway/release/nginx/smoke **78/78**, landing и полный frontend
  production build — PASS; targeted Playwright root smoke **3/3** в Chromium,
  WebKit и Firefox. Общий frontend unit suite имеет 10 существующих
  падений в `packages/app-shell` (auth/realtime/session-management), не связанных
  с landing; snapshots не обновлялись.
- Backend, миграции и production deploy остаются вне этого инкремента. Перед
  публикацией на сервере нужно добавить landing locations из
  [`vmshpwa.conf.template`](../../deploy/nginx/vmshpwa.conf.template) и один раз
  исправить права уже созданного release.

## Phase 6 checkpoint: immediate Telegram review delivery — 3 August 2026

- После успешного Staff review Student получает одно тихое личное сообщение с
  provenance всех веток синонимичного кейса, verdict и комментарием; все
  успешно собранные annotation composite отправляются PNG-фотографиями.
- Запрос читает только committed review. Idempotent replay не дублирует
  Telegram, а storage/render/API failure не откатывает SQLite review/result и
  не мешает тексту либо другим готовым картинкам.
- Реализация не создаёт очередь или общий delivery framework:
  [`db_methods/pwa/review_telegram.py`](../../../db_methods/pwa/review_telegram.py)
  содержит два коротких read-запроса, policy и русские формулировки остаются в
  HTTP/Telegram boundary.
- Proof:
  [`phase6-review-telegram-delivery-2026-08-03.md`](../../../pwa_tests/reports/phase6-review-telegram-delivery-2026-08-03.md).
- Verification: focused delivery/composite **7 pass**; full eight-worker PWA
  Python suite **1634 pass / 6 skip** in **75.22 s**; Ruff and diff checks pass.

## Phase 1 checkpoint: account provisioning UI — 3 August 2026

- Admin-only Student and Family TSV preview/apply is connected to the real
  provisioning API at `/staff/users?tab=imports`; course enrollment remains a
  separate batch.
- Account/runtime-scoped `localStorage` keeps unsent TSV through reload and is
  cleared only after a complete creation receipt. Preview/receipt contracts do
  not expose credentials or Family email addresses.
- Proof: frontend unit **603 pass**, Storybook browser interaction/a11y **259
  pass**, lint/typecheck/production build pass. Desktop and 390×844 were
  inspected manually; snapshots were not updated.
- Report:
  [`phase1-account-provisioning-staff-ui-2026-08-03.md`](../../../pwa_tests/reports/phase1-account-provisioning-staff-ui-2026-08-03.md).

## Phase 10 checkpoint: searchable Staff audit — 2 August 2026

- Added append-only migration `0075.pwa_staff_audit`; existing domain journals stay
  authoritative and no general event framework was introduced.
- Real admin-only `/staff/audit` now has strict URL/API contracts, object and request
  search, stable cursor paging, actor/request ID and safe primitive before/after.
- Current transactional coverage: account/Family lifecycle, credential/status,
  course enrollment and problem-import apply/rollback. Remaining Staff mutations are
  explicitly open and listed in
  [`phase10-staff-audit.md`](../../../pwa_tests/reports/phase10-staff-audit.md).
- Proof: Python focused **62 pass**; frontend unit **577 pass**; Storybook browser/a11y
  **231 pass**; production E2E **84 pass / 12 expected skip** across three browsers.
- Story IDs: `Pages/Staff/Audit--SearchableTimeline`,
  `Pages/Staff/Audit--EmptySearch`. Visual snapshots were not updated.
- Course/group catalog coverage adds `course.created/updated` and
  `group.created/updated`; focused aiohttp **7 pass**, frontend unit **3 pass** and
  Storybook interaction/a11y **2 pass**. A forced audit failure rolls the catalog
  mutation back instead of leaving an unjournaled change.
- Telegram binding coverage adds create/update/disable/restore/verify with safe
  destination/status diffs and atomic rollback. Full checkpoint: Python PWA **1523
  pass / 5 skip**, frontend unit **578 pass**, focused Storybook **2 pass**;
  lint/typecheck/production build — PASS.

## Состояние документов

| Документ/этап       | Статус                         | Решение/блокер                                                                                                                                                                          |
| ------------------- | ------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Инженерный контракт | draft for approval             | Формат proof описан; фактически заполняется при реализации                                                                                                                              |
| Решения и границы   | accepted planning input        | Исходный опросник и 4 развилки внешнего ревью закрыты в `17-open-questions.md`                                                                                                          |
| Модель данных       | revised planning input         | Cutoff, season backfill, analytics snapshots и reaction migration уточнены                                                                                                              |
| API/events/files    | accepted planning input        | Batch move, cross-group confirm и classroom history зафиксированы                                                                                                                       |
| Этап 0              | in progress                    | Runtime/schema/seed/auth/storage, one-origin functional E2E 72/72 и live Telegram bind/send/edit/delete готовы; остаются visual owner gate и telemetry gaps                             |
| Этап 1              | in progress                    | Auth/HTTP/WebSocket и proxy boundary зафиксированы в `1aad776`, browser auth E2E 60/60 готовы; остаются server nginx-t/live rate smoke и production controlled import                   |
| Этап 2              | Phase 2A–2E + browser E2E      | Matching/metadata, PDF, пакетная загрузка и content E2E 3/3 проверены; открыты production parity/backfill и owner visual gate                                                           |
| Этап 3              | Phase 3A–3H reading slice      | Course/lesson/home, canonical task/reveal, owner-isolated cold-offline reading и long-corpus KaTeX budget проверены; открыт только visual owner gate                                    |
| Этап 4              | Phase 4A–4G functionally ready | Domain/API, draft/outbox, Student submit, Staff recheck и общая PWA/Telegram policy готовы; открыт только visual owner gate                                                             |
| Этап 5              | Phase 5A–5I browser + live S3  | Server/browser vertical, guarded S3, atomic replacement, append-only reassignment, Staff media/client, correction UI и media corpus готовы; legacy backfill и общий visual gate открыты |
| Этап 6              | functionally ready             | Review/workspace/reactions/corrections/support и production E2E доказаны; открыты owner visual gate, support attachments и Telegram continuation                                        |
| Этап 7              | Phase 7A catalog accepted      | Каталог аудиторий прошёл storage/API/Staff UI/E2E; layout, assignment, delivery и oral gates остаются открыты                                                                           |
| Этапы 8–11          | planned with gates             | Продуктовые развилки закрыты; readiness доказывается phase proof, а не дополнительным опросом                                                                                           |
| Design system       | phases 5–7 ready for review    | [Этапы связаны](18-design-implementation-map.md) с components/story IDs; остался ручной owner gate                                                                                      |
| Multi-course model  | schema + verified prototype    | Phase-1 course/access schema и UI prototype готовы; backend repository/HTTP и миграции последующих фаз ещё выполняются                                                                  |

## Журнал решений

| Дата       | ID       | Решение                                                                                                  | Последствие                                                                                                                                                    |
| ---------- | -------- | -------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 2026-07-23 | PLAN-001 | Этапы строятся как вертикальные работающие срезы                                                         | Backend/UI/contracts/tests/docs закрываются вместе                                                                                                             |
| 2026-07-23 | PLAN-002 | E2E и visual regression выполняются на production Vite bundles за one-origin gateway                     | Dev server остаётся для локальной разработки; gateway моделирует общий host/API/WS, но не заменяет deploy smoke                                                |
| 2026-07-23 | PLAN-003 | A11y gate остаётся для Staff                                                                             | Не создаётся отдельный исключённый контур                                                                                                                      |
| 2026-07-23 | PLAN-004 | Reconnect всегда вызывает authoritative refetch                                                          | WS cursor не используется как доказательство отсутствия пропусков между workers                                                                                |
| 2026-07-23 | PLAN-005 | `_vmsh_examples` — golden corpus, `_external_pipelines` — characterization references                    | Их не редактируют и не импортируют в новый production runtime                                                                                                  |
| 2026-07-24 | PLAN-006 | Первый выпуск: сезон 2025–2026, занятия 39–41, все три уровня                                            | Вертикальные этапы должны привести к полному онлайн-занятию, а не к pilot одной группы                                                                         |
| 2026-07-24 | PLAN-007 | Telegram остаётся двусторонним рабочим каналом на переходе                                               | Треды и provenance объединяют PWA и Telegram; все external pipelines сохраняются до cutover                                                                    |
| 2026-07-24 | PLAN-008 | Печатный/очный раздел, общий Staff→Telegram publisher и AI перенесены во вторую версию                   | Узкая персональная classroom delivery позже выделена отдельным v1-исключением; остальные функции не блокируют первый выпуск                                    |
| 2026-07-24 | PLAN-009 | Исходный продуктовый опросник закрыт                                                                     | Новые вопросы добавляются только при реальной развилке реализации                                                                                              |
| 2026-07-24 | PLAN-010 | Ответы разнесены по модели, API, этапам и эксплуатационным документам                                    | Этап 0 можно начинать без повторного сбора продуктовых требований                                                                                              |
| 2026-07-24 | PLAN-011 | Аудитории разделены на глобальный каталог, наследуемую схему по группам и версионируемый план школьников | Этап 7 получает admin-only catalog/layout/preview/confirm, без capacity и drag-and-drop; initial Excel используется один раз через dry-run/import              |
| 2026-07-25 | PLAN-012 | Classroom planner использует compact single/bulk select и локально накопленный draft                     | Каждая смена select не пишет на server; reload восстанавливает draft, batch-save атомарен, cross-group move требует confirmation                               |
| 2026-07-25 | PLAN-013 | Classroom read model показывает age/class/auto-strength, aggregates, fuzzy search и history              | `users`/`student_strength` остаются источниками; nullable values не входят в averages; confirmed plans образуют историю                                        |
| 2026-07-25 | PLAN-014 | Незавершённую значимую работу Student/Staff нельзя терять                                                | `localStorage` хранит serializable drafts, Dexie — blobs/outbox; очистка только после receipt/confirm/discard                                                  |
| 2026-07-25 | PLAN-015 | Ребёнок никогда не отмечается на групповой статистике                                                    | Self marker, percentile и словесное сравнение с группой запрещены в Student/Family charts                                                                      |
| 2026-07-25 | PLAN-016 | Test input повторяет 23 legacy-типа и `strip()+fullmatch`                                                | Видимая format error; tuple без «Отправится»; list preview после parsing; select передаёт видимый label                                                        |
| 2026-07-25 | PLAN-017 | Review — хронологическая основная колонка, teacher controls компактны, но подписаны                      | Evidence, существующий thread и новый ответ не разделяются на три независимые панели                                                                           |
| 2026-07-25 | PLAN-018 | Condition, hint и solution публикуются независимо; metadata имеет task/answer dropdown                   | У каждого artifact своё «сейчас»/расписание/rollback; TSV paste сохраняется                                                                                    |
| 2026-07-25 | PLAN-019 | Условия идут полноценным Telegram Rich Message, а broadcast editor переносится во вторую фазу            | Stories используют text/math/lists и export corpus; v1 не имитирует рассылку, отдельная submission-квитанция отсутствует                                       |
| 2026-07-25 | PLAN-020 | Client format validation не мешает незавершённому вводу                                                  | `TestAnswer` раскрывает ошибку после blur/submit; fixed tuple остаётся спокойным между слотами; weekday использует кнопки `пн–вс`                              |
| 2026-07-25 | PLAN-021 | Authoritative schema — применённые migrations + проверенный inventory, не старый snapshot в одиночку     | Этап 0 проверяет/перегенерирует `docs/db_structure.sql`; runtime schema drift обнаруживается до business migration                                             |
| 2026-07-25 | PLAN-022 | SQLite concurrency и migration lifecycle становятся обязательным ADR до первой бизнес-миграции           | Нет общего concurrent connection/`await` в transaction; yoyo запускается отдельным deploy command, startup только проверяет version                            |
| 2026-07-25 | PLAN-023 | Submission cutoff и solution publication моделируются раздельно                                          | `lesson_windows.submission_closes_at` существует заранее; policy переноса расписания вынесена в `SCHEDULE-01`                                                  |
| 2026-07-25 | PLAN-024 | Legacy analytics переносится versioned full-run snapshots, история текущего сезона backfill-ится         | `a53`/`a54` получают numerical parity; занятия 1–38 не исчезают из history/progress из-за отсутствия новых publication rows                                    |
| 2026-07-25 | PLAN-025 | Каждый внешний процесс имеет legacy bridge и конечного внутреннего владельца                             | `a00_dates`, `a03`, print/analytics/old-site chains добавлены в register; «не v1» больше не означает бессрочно внешний процесс                                 |
| 2026-07-25 | PLAN-026 | Внешнее ревью открыло четыре новые продуктовые развилки без блокировки этапа 0                           | Production cutover соответствующих фаз ждёт ответов `SCHEDULE-01`, `AUTH-01`, `CLASSROOM-01`, `RETENTION-01`                                                   |
| 2026-07-25 | PLAN-027 | У каждого этапа есть явный design implementation map                                                     | Phase-файл ведёт к компонентам, story source и URL; изменение accepted UI обновляет код, story, карту и status вместе                                          |
| 2026-07-26 | PLAN-028 | Internal teacher reactions получают компактный Mod+Alt shortcut                                          | `⌘/Ctrl + Alt + 1…4` работает при фокусе в комментарии; простой Mod+digit оставлен браузеру, `AltGraph` игнорируется                                           |
| 2026-07-26 | PLAN-029 | Внешние converter binaries задаются общим backend config и разрешаются через service `PATH`              | Defaults: `pdf2svg`, `cwebp`, `pdflatex`, `magick`; absolute override/`None` явны, readiness/deploy проверяют capabilities до первого задания                  |
| 2026-07-26 | PLAN-030 | S3 adapter использует общий profile-aware config: Beget test, Hetzner production target                  | Test/production secret sources раздельны; agent/E2E остаются filesystem, secrets всегда redacted; legacy Beget default не считается PWA production default     |
| 2026-07-26 | PLAN-031 | Telegram channel destinations хранятся в course/group `telegram_bindings`                                | `@vmsh179devbot` + private test channel используются opt-in; Bot API canonical ID/rights проверяются, token остаётся config-only, unit/E2E offline             |
| 2026-07-26 | PLAN-032 | Принята иерархия season→course→group→lesson, логические синонимы и multi-course in-person events         | Фазы 1–11 дополнены; Storybook prototype реализован; production backend/migrations остаются невыполненными                                                     |
| 2026-07-27 | PLAN-033 | Cutoff и solution schedule независимы; реальные accounts валидны, тестовые исключаются preflight-ом      | `SCHEDULE-01` и `AUTH-01` закрыты; deadline меняется только отдельным audited action, неизвестный account не активируется молча                                |
| 2026-07-27 | PLAN-034 | Classroom confirm и notification разделены                                                               | Admin после preview явно выбирает PWA/Telegram; Student получает personal delivery, Family только state refetch, auto-resend отсутствует                       |
| 2026-07-27 | PLAN-035 | Print остаётся отдельным разделом v2, media retention — бессрочная admin-managed policy                  | V1 не обещает `a11`–`a14` compatibility export; очистка только manual manifest-driven с preview/audit                                                          |
| 2026-07-27 | PLAN-036 | Opt-in test S3/Telegram side effects явно разрешены владельцем                                           | Disposable test-prefix objects и synthetic test-channel messages можно create/read/edit/delete; production resources запрещены                                 |
| 2026-07-27 | PLAN-037 | PWA runtime использует connection-per-operation и никогда не мигрирует SQLite при startup                | Отдельная maintenance-команда применяет yoyo под lock и включает WAL; startup fail-closed проверяет migration IDs/hash/WAL, legacy auto-migrate пока сохранён  |
| 2026-07-27 | PLAN-038 | PWA maintenance-команды выбирают состояние только через явный проверенный профиль                        | Guard выполняется до импорта legacy config; неизвестные CLI-аргументы отклоняются, поэтому опечатка не может выбрать fallback DB или credential loader         |
| 2026-07-27 | PLAN-039 | Converter readiness подтверждается разрешением executable и поведенческим smoke                          | Fixed argv без shell, bounded output/timeout/process-group cleanup; synthetic TikZ→SVG и raster→WebP проверяют результат, HEIC capability отражается отдельно  |
| 2026-07-27 | PLAN-040 | Legacy rules защищаются executable characterization, corpus — schema-light manifest                      | 23 answer types, verdict/reaction/queue/synonym semantics зафиксированы; 54 source files покрыты hash/encoding/structure без дублирования содержания           |
| 2026-07-27 | PLAN-041 | Schema baseline — migration-derived inventory, а live drift остаётся явным                               | Head содержит 94 product objects; live lag 0039/0040 и 12 derived objects фиксируются без записи; product rows не выбираются, DDL/defaults только fingerprint  |
| 2026-07-27 | PLAN-053 | Browser user identity отделена от account identity и legacy integer FK                                   | `users.public_id` nullable только до controlled activation; `userId`/`studentId` никогда не подменяются `accountId`, отсутствие значения закрывает web-доступ  |
| 2026-07-27 | PLAN-054 | Session reference каноничен на всех cookie/token/storage границах                                        | Только 32 lowercase hex принимаются parser, signed access codec и repository; корректная подпись не легализует иной alias                                      |
| 2026-07-27 | PLAN-055 | Unsafe browser request защищён до появления cookie                                                       | Login тоже требует same-origin evidence; safe set ровно GET/HEAD/OPTIONS, TRACE fail-closed                                                                    |
| 2026-07-27 | PLAN-056 | Teacher authorizes только authoritative resource scope                                                   | Bare capability/collection и сочетание произвольного student ID с разрешённым request group fail-closed; collection фильтруется в SQLite                       |
| 2026-07-27 | PLAN-057 | Forwarded chain — явная deploy-конвенция, а не доверие к произвольному header                            | Trusted proxy заменяет client headers; точные hops и first-element external host/proto доказываются production-like nginx test                                 |
| 2026-07-27 | PLAN-058 | Telegram UI scheduled queue является внешним mutable state до публикации                                 | Перед передачей destination Staff scheduler нужен inventory и explicit retain/cancel+recreate/cancel с доказательством no-gap/no-duplicate                     |
| 2026-07-27 | PLAN-059 | Legacy `cor_ans_checker` сначала характеризуется по фактической execution boundary                       | `is_py_func`/restricted globals/`run_py_func_checker` получают synthetic allow/deny/error/cache corpus; это trusted-admin compatibility, не sandbox            |
| 2026-07-27 | PLAN-060 | Cookie-authenticated WebSocket GET всегда проверяет browser Origin                                       | Handshake — исключение из safe-method policy; revoke/logout закрывает session sockets, long-lived connection перепроверяет server state                        |
| 2026-07-27 | PLAN-061 | Ошибочно приложенный материал исправляется append-only проекцией                                         | Owner: teacher + target history; default: scoped admin/post-review/preview; bytes, IDs, evidence и verdict не переписываются                                   |
| 2026-07-27 | PLAN-062 | Combined synonym review выбирает target только по серверному порядку                                     | Последняя `server_received_at`; internal submission ID — детерминированный tie-break, client time не влияет                                                    |
| 2026-07-27 | PLAN-063 | Annotation хранит нормализованные marks, но не состояние просмотрщика                                    | Owner core: pencil/eraser/text/arrow/rectangle/rotation; optional implementation: highlight/palette; zoom/pan локальны                                         |
| 2026-07-27 | PLAN-064 | Ранее подтверждённый аккаунт может читать свой кеш в offline-unverified                                  | Owner: offline reading/logout warning; default: session expiry, auth-before-sync и account cleanup общего устройства                                           |
| 2026-07-27 | PLAN-065 | Delivery observability различает channel success и частичный охват                                       | Owner: counters/partial lists; default: explicit retry только failed recipient/channel pairs без дублей success                                                |
| 2026-07-27 | PLAN-066 | Исторические credential/PII artifacts не становятся новыми fixtures или auth source                      | Migration `0038` и private logs остаются в истории по принятому owner risk; новый pipeline их не копирует и не выводит                                         |
| 2026-07-27 | PLAN-067 | Legacy state backfill не выдумывает события и связи review                                               | Повторные одинаковые `G`/`O` схлопываются; discussion импортируется одним thread без искусственного message→verdict round                                      |
| 2026-07-27 | PLAN-068 | Live Telegram smoke закреплён за owner-provided test-only destination                                    | Canonical `chat.id=-1003913815635` всё равно перепроверяется Bot API; token/production destinations не попадают в код или отчёт                                |
| 2026-07-27 | PLAN-069 | Production-size rehearsal начинается только с безопасной копии                                           | Source `db/vmsh.db` не мутируется; в isolated copy Faker заменяет имена/фамилии, а backup signal не заменяет полный restore rehearsal                          |
| 2026-07-27 | PLAN-070 | Production PWA mode задаётся `pwa-production` либо точным `PROD=true` marker                             | Prototype запрещён; explicit HTTPS origins и `Secure` cookies обязательны, legacy Telegram/Google loader не вызывается                                         |
| 2026-07-27 | PLAN-071 | Trusted proxy поддерживает explicit TCP CIDR либо exact filesystem Unix socket                           | AF_UNIX/local сам по себе не trusted; `sockname`, exact hops и origin обязательны, nginx заменяет headers; live nginx proof не подменяется structural tests    |
| 2026-07-27 | PLAN-042 | `baseline-v1` строится вне target и устанавливается только после полной проверки                         | Exact profile/path allowlist, scoped FK gates, purge+VACUUM credentials, shared-runtime/exclusive-maintenance lock и durable atomic replace                    |
| 2026-07-27 | PLAN-043 | Auth/workload preflight читает реальные источники fail-closed и публикует только безопасные агрегаты     | Same-fd bytes/hash и alias rejection защищают inputs; auth query использует deserialize snapshot; explicit check ловит missing/stale report-pair               |
| 2026-07-27 | PLAN-044 | Live S3 разрешён только после pinned test-target check; SDK boundary всегда редактирует provider errors  | Beget test identity закреплена SHA-256, full provider key проверяется после prefix, optional checksums=`when_required`; Hetzner остаётся production target     |
| 2026-07-27 | PLAN-045 | Core NATS — transient fan-out с per-audience cursor и обязательным authoritative reconnect refetch       | Full startup cleanup, reconnect close fallback, bounded WS send/close-before-untrack, graceful shutdown и checked local smoke закрывают lifecycle              |
| 2026-07-27 | PLAN-046 | Live Telegram test использует двухшаговый trust flow                                                     | Read-only bind неизменно пишет owner-only local SQLite; write-smoke не принимает destination из environment и повторно проверяет private channel identity      |
| 2026-07-27 | PLAN-047 | Реестр внешних процессов разделяет наблюдаемый legacy-контур и ещё не реализованный target               | 48 процессов имеют invocation/upstream/side effects/recovery/transition; cutover возможен только после phase proof и явного решения                            |
| 2026-07-27 | PLAN-048 | Runtime namespace принадлежит серверу, а E2E моделирует один production origin                           | Runtime проверяется до router; namespace, PWA scopes/caches и gateway 5380 разделяют аудитории                                                                 |
| 2026-07-27 | PLAN-049 | Runtime wire contract версионируется отдельно от browser storage                                         | Неизвестная версия fail-closed; additive v1 fields допустимы при rolling deploy; namespace version меняется только с миграцией локальных данных                |
| 2026-07-27 | PLAN-050 | PWA update recovery не зависит от runtime и IndexedDB gates, а E2E suite сериализован                    | Worker может обновить сломанный startup; единый flock охватывает production build, seed, shared ports и Playwright                                             |
| 2026-07-27 | PLAN-051 | Phase-0 one-origin gateway ещё не является trusted-proxy/auth моделью                                    | Phase 1 задаёт public origin и доверенные proxy hops; spoofed `Forwarded`/`X-Forwarded-*` входят в обязательные negative tests                                 |
| 2026-07-27 | PLAN-052 | Phase-1 auth использует Argon2id, audience-salted signed access и soft-revoked rotating refresh sessions | Current defaults rehash после login; HMAC refresh/throttle keys живут только в SQLite; точная модель и источники закреплены в ADR 0003                         |
| 2026-07-27 | PLAN-072 | WebSocket становится routable только после authoritative pending-handshake                               | Session tombstone закрывает close-before-register; initial cursor frame атомарен с audience fan-out, invalidation не опережает handshake                       |
| 2026-07-27 | PLAN-073 | Stored Argon2id ограничен fail-closed resource envelope                                                  | Malformed и чрезмерно дорогой encoding выбирают startup dummy; unknown/invalid paths делают один instrumented Argon verify без wall-clock oracle               |
| 2026-07-27 | PLAN-074 | Telegram renderer закреплён на проверенном Bot API 10.2 Rich HTML dialect                                | До send проверяются 32 768 UTF-8 characters, 500 blocks, nesting 16, 50 media и 20 columns; dialect/limits входят в provenance и live corpus                   |
| 2026-07-28 | PLAN-075 | Publication wall time разрешает только backend в timezone группового занятия                             | Browser передаёт `scheduledLocalTime` + IANA `businessTimezone`; `zoneinfo` переводит в UTC и отклоняет DST gap/fold, `Date.parse()` не используется           |
| 2026-07-28 | PLAN-076 | Written evidence хранит final WebP, а порядок использует sparse ordinal                                  | Durable attachment принимает submission WebP ≤1920; лимит 10 проверяет trigger, временный высокий ordinal позволяет swap при immediate SQLite UNIQUE           |
| 2026-07-28 | PLAN-077 | Каждая Student written entry фиксирует exact problem revision                                            | Thread остаётся общей историей после правки условия; новая entry не теряет provenance, legacy teacher/Telegram backfill может оставить revision nullable       |
| 2026-07-28 | PLAN-078 | Written draft синхронизируется отдельно от окончательной отправки                                        | Поздняя offline-доставка не теряет материал; cutoff применяется при submit к immutable client time, server time и suspicious-clock сохраняются                 |
| 2026-07-28 | PLAN-079 | Submission photo хранится только как уникальный final WebP после server re-encode                        | Source не попадает в durable storage; DB failure компенсирует object delete, filesystem использует owner-only mediaPath, production может отдать public S3 URL |
| 2026-07-28 | PLAN-080 | До review-lock страницы можно удалить и переупорядочить; после lock evidence неизменяемо                 | Удаление сразу убирает projection и ставит asset deleted_at; final object остаётся под admin-managed retention до отдельной manifest-driven очистки            |
| 2026-07-28 | PLAN-081 | Written draft делит serializable state и бинарные страницы между localStorage и Dexie                    | Reload сохраняет текст/порядок/server IDs; portable ArrayBuffer обходит WebKit Blob/IDB failure; source хранится только до server fallback receipt             |
| 2026-07-28 | PLAN-082 | Pre-review исправление — новая entry и атомарная логическая замена                                       | Старое evidence не перепривязывается; durable replacement intent переживает reload, а после lock доступно только продолжение треда                             |

## Текущий инкремент этапа 0

- Реализация: `db_methods/pwa/migrations.py`, `db_methods/pwa/connection.py`, `main.py`, `vmshpwa/scripts/{runtime_guard,migrate_runtime,seed_runtime}.py`.
- Fault/API tests: `pwa_tests/integration/test_migration_lifecycle.py`, `pwa_tests/integration/test_sqlite_concurrency.py`, `pwa_tests/test_app_factory.py`, `pwa_tests/test_config_safety.py`, `pwa_tests/test_maintenance_commands.py`.
- Проверено 27 июля 2026: 15 целевых migration/concurrency/factory/config tests и 7/7 maintenance guard tests; полный `pwa_tests` — 33/33 PASS на Python 3.14.3.
- Toolchain increment: `helpers/pwa/toolchain.py`, `vmshpwa/scripts/toolchain_{preflight,smoke}.py`, unit/integration tests и `pwa_tests/reports/toolchain-local.md`; локальный preflight и оба converter chains PASS, HEIC advertised.
- Characterization increment: 63/63 domain tests PASS; `vmshpwa/scripts/golden_corpus.py check` подтвердил 54/54 source files. Дополнительно исполняемо зафиксированы `G`/`O` строки `user_changes_log`, повторные no-op commands, nullable `written_tasks_discussions.chat_id/tg_msg_id` и отсутствие достоверной связи legacy message→review round. Владелец закрыл правила backfill: no-op `G`/`O` схлопываются, а historical discussion остаётся единым thread без выдуманной связи с review round. Подробности: `pwa_tests/reports/legacy-characterization.md`.
- Schema/seed inventory: после additive migrations `0041`–`0043` head содержит
  192 product objects с hash `0a7593ea…`; generated inventory/snapshots и
  `make pwa-schema-check` согласованы. Последний live read-only report был снят
  до `0041`, поэтому остаётся историческим Phase-0 evidence и не выдаётся за
  текущую production readiness; `db/vmsh.db` при этом инкременте не открывалась
  на запись.
- Seed/lifecycle-lock increment: два последовательных актуальных agent seed запуска дают digest `782b4051…`; synthetic Family/auth/course/access/scopes и отдельные browser user IDs материализованы, но sessions/audit/throttle/consumed-refresh/history намеренно пусты. Пять Argon2id hashes проверяются только против test-harness credentials; production/path guards и очистка migration-carried credentials сохранены. Exhaustive answer examples совпадают с legacy regex; scoped FK gate, SQLite recovery и lifecycle locking остаются покрыты. Подробности: `pwa_tests/reports/baseline-v1.md` и ADR 0002.
- Auth/workload increment: 25/25 focused tests PASS; `make pwa-auth-preflight-check` подтвердил aggregate lower bound 36/1617 Student rows без source values; `make pwa-workload-profile-check` подтвердил 19 raw files, 176713 canonical events и 37408 traces, same-fd source checks и 0 unreviewed labels. Unknown user types, deserialize failure, source-change, symlink/hard-link/duplicate-inode и missing/stale report pairs закрыты. Отчёты: `pwa_tests/reports/{auth-preflight,workload-profile}.{json,md}`.
- Storage increment: 86 focused tests PASS; filesystem atomicity/no-follow, fail-closed S3 config, secret-file race protection, redacted errors, collision-safe live probes, Beget/Hetzner URL rules, pinned live identity и checksum compatibility закрыты. Live Beget test-bucket runs `codex-phase0-20260727-f6c821d9` и `codex-phase0-20260727-collision-safe` прошли put/private-read/public-GET/delete acknowledgement. Отчёт: `pwa_tests/reports/object-storage-phase0.md`.
- Realtime/Telegram harness increment: 74 focused tests PASS. NATS local fan-out/isolation smoke PASS; reconnect/cleanup/readiness, partial-startup cleanup, per-audience cursor, bounded fan-out с close-before-untrack, WebSocket shutdown, strict JSON/event boundary и RecordingBot/two-step binding покрыты. Актуальные полные `make pwa-test` totals приведены в runtime/browser increment ниже. 27 июля guarded live bind подтвердил test-only bot/private channel identity и права, а synthetic lifecycle успешно выполнил send/edit/delete с cleanup без остаточного сообщения. Rich Message proof относится к Phase 2. Отчёты: `pwa_tests/reports/phase0-{nats-local,live-integration-2026-07-27}.md`.
- External-process register increment: 48 current/reference процессов, 36 repository artifacts, два runbook и шесть отсутствующих dependencies описаны без PII; неатомарное окно restore старой DB и обязательный credentials workbook почтового pipeline зафиксированы явно; current/target и `legacy_bridge|v1_cutover|later_internalization` разведены. 7 focused structural/link/privacy/semantic tests PASS. Документы: `21-external-process-register.md`, `16-external-artifacts.md`; fixture: `pwa_tests/fixtures/external-process-register.v1.json`.
- Runtime/browser isolation increment: explicit v1 Python↔Zod wire/error
  fixtures с rolling-deploy policy, bounded pre-router bootstrap, safe
  localStorage, canonical Dexie namespaces с blocked/timeout/close recovery,
  update recovery outside startup gates, scope-versioned Workbox caches и
  lock-aware one-origin production E2E реализованы. Focused Python — 97 PASS;
  `make pwa-test` — Vitest 68 PASS и Python 461 PASS / 1 intentional skip;
  lint/typecheck/build PASS; Storybook browser mode — 32 files / 140 PASS.
  `make pwa-e2e-functional` — 72/72 PASS в Chromium/WebKit/Firefox, включая
  active-worker path denylist, incompatible-runtime update и obsolete-cache
  cleanup; после static-suffix и external-network hardening итоговый
  `make pwa-e2e-runtime` повторно дал 60/60 PASS во всех трёх engines. Startup
  stories: `product-app-startup--runtime-loading`,
  `product-app-startup--runtime-rejected`,
  `product-app-startup--offline-storage-unavailable`. `make pwa-visual` без
  update: Staff 3 PASS; Student current-week 3 ожидаемых stale diff 390×1188 →
  390×1615. Owner approval остаётся обязательным. Отчёт:
  `pwa_tests/reports/runtime-isolation-phase0.md`.
- Этап 0 не закрыт: workload пока не измеряет concurrent sessions/write latency/photo bytes/outbox/`SQLITE_BUSY` budget; впереди visual owner approval. Live Telegram bind и synthetic send/edit/delete smoke пройдены 27 июля. Trusted-proxy/public-origin и spoofed-forwarded matrix явно переданы в Phase 1 и не считаются доказанными текущим gateway.

## Текущий инкремент этапа 2

- Phase 2A реализует только schema/domain/repository boundary: additive
  [`0041`](../../../migrations/0041.pwa_content_lessons.sql), последующие
  concurrency/audit migrations
  [`0042`](../../../migrations/0042.pwa_content_concurrency.sql) и
  [`0043`](../../../migrations/0043.pwa_lesson_window_audit.sql), pure rules
  [`models/pwa/content.py`](../../../models/pwa/content.py) и
  connection-per-operation repository
  [`db_methods/pwa/content.py`](../../../db_methods/pwa/content.py).
- Зафиксированы independent course/group lessons, four-field versioned schedule
  с immutable materialization provenance, append-only revision/problem/synonym
  history, content-addressed assets и atomic publication
  schedule/replace/rollback/reveal invariants.
- Проверено 27 июля 2026: 48 focused domain/repository/migration PASS; 69 PASS
  вместе с полным schema-inventory suite; `make pwa-schema-check`, Ruff check и
  format-check PASS. Exact up/down/up не меняет legacy rows, а
  `db/vmsh.db` не мигрировалась.
- Proof: [`phase2-content-schema.md`](../../../pwa_tests/reports/phase2-content-schema.md).
  Последующие gate закрыли HTTP/UI и safe historical backfill tooling;
  production backfill apply и перечисленные ниже product gates остаются
  открыты, Phase 2 целиком не принят.
- Phase 2B добавляет side-effect-free compiler в
  [`helpers/pwa/content`](../../../helpers/pwa/content): bounded UTF-8/CP1251
  scanner, typed AST, positional diagnostics, role-isolated web/Telegram
  renderers, `WebContentDocument v1` и fixed-toolchain asset converters.
- Corpus gate 2024–2025 (13 августа 2026) прогнал **218** файлов условий и
  решений (**2481** problem nodes); **36** агрегатных placeholders исключены
  явно. Corpus-driven compatibility снизил blocking diagnostics с **1398** до
  **25** в **14** файлах и устранил все `latex.unknown_macro`; оставшиеся
  ошибки — повреждённые bytes, реальная непарность, три legacy `picture` и два
  одиночных слеша. Все позиции:
  [`phase2-content-archive-2024-2025-errors.md`](../../../pwa_tests/reports/phase2-content-archive-2024-2025-errors.md).
- Текущий Phase 2B increment (13 августа 2026) добавляет семантические
  `\объявление…\кобъявление` и
  `\важноеОбъявление…\кважноеОбъявление`: typed AST, fail-closed парный
  разбор, WebContentDocument callout, Telegram Rich blocks и адаптивную
  Student/Staff вёрстку. Focused Python **92 PASS**, content/contract Vitest
  **37 PASS**, Storybook **10 PASS**, type/lint/format и characterization
  **PASS**; публикационный E2E объявления прошёл в Chromium, WebKit и Firefox.
  Proof:
  [`phase2-content-announcements-2026-08-13.md`](../../../pwa_tests/reports/phase2-content-announcements-2026-08-13.md).
- Golden characterization: 30/30 TeX sources, 334 problem nodes, 0 errors и
  одно ожидаемое legacy-layout warning; report:
  [`phase2-content-compiler.md`](../../../pwa_tests/reports/phase2-content-compiler.md).
  Shared Python/Zod fixture:
  [`python-compiler-preview.v1.json`](../../packages/contracts/fixtures/content/python-compiler-preview.v1.json).
- Pure compiler/Telegram/characterization tests — 69 PASS; asset
  boundary tests — 15 PASS; converter→shared ObjectStorage→repository service —
  5 PASS; WebContentDocument contract — 18 PASS; real local TikZ→SVG and
  raster→WebP smoke with the configured executable paths — 1 PASS.
  Support/limitations:
  [`content-compiler-support-matrix.md`](../../docs/content-compiler-support-matrix.md).
- Phase 2C зафиксирован revisions `1aad776` и `866e3fe`: authenticated
  aiohttp content runtime, compile retry/lease, concurrency-safe publication,
  scheduler, readiness/cutoff gates, bounded history и три audience frontend.
  Staff умеет продолжить загруженную revision после reload, явно выбрать
  предыдущую `ready` revision для rollback, подтвердить опасное действие и
  одновременно сравнить PWA/Telegram preview; Student/Family получают update
  marker при смене revision.
- Schedule wire server-authoritative: UI передаёт `scheduledLocalTime` и
  authoritative IANA `businessTimezone`, а Python `zoneinfo` преобразует wall
  time в UTC и отклоняет DST gap/fold. `lesson_window_changes` из `0043`
  неизменно хранит actor/request/before/after; solution schedule/publish не
  допускается без отдельно заданного cutoff.
- Чистый compiler принимает для web asset только строгий descriptor (public
  ID, SHA-256, безопасный URL, media type, dimensions); hash и URL не могут
  разойтись как независимые источники истины.
- Полный checkpoint 28 июля: `make pwa-lint`, `make pwa-typecheck`,
  `make pwa-storybook-test`, `make pwa-build`, `make pwa-schema-check` — PASS;
  frontend unit — **218 PASS**, Python PWA — **1028 PASS / 3 skip / 1 warning**,
  Storybook browser — **167 PASS**, schema inventory — **192 product objects**;
  production-build `make pwa-e2e-auth` после deep-link default fix — **60/60
  PASS** в Chromium, WebKit и Firefox. Это auth regression, не content E2E.
- Phase 2D (`43b0323`, `08a8d0b`, `d39141d`) добавляет authenticated asset
  inventory/upload, content-addressed WebP/SVG/TikZ storage, immutable local
  media URL, Staff recovery states, PWA cache/proxy и provider-first PDF
  persistence. Regression: 302 Python asset, 10 PDF persistence, 21 frontend
  unit и 17 Storybook browser tests; Ruff/ESLint/typecheck/production builds
  PASS. Proof:
  [`phase2-content-assets-http.md`](../../../pwa_tests/reports/phase2-content-assets-http.md).
- Phase 2E backend добавляет полный immutable positional matching, отдельный
  review ETag, atomic condition metadata-grid confirmation и legacy `problems`
  projection. Teacher получает `403`, stale write — `409`; condition требует
  matching + metadata, а independently compiled hint/solution — собственного
  matching без дублирования task metadata. Domain/repository/real-aiohttp
  suite — **111 PASS**, Ruff — PASS. Proof:
  [`phase2-problem-review-api.md`](../../../pwa_tests/reports/phase2-problem-review-api.md).
- Phase 2E frontend boundary добавляет strict Zod full-batch contracts для
  matching/condition metadata, все 23 historical answer types, GET/PUT client,
  exact `If-Match`, body/header ETag consistency и query hooks. Два package
  typecheck, ESLint и **24 unit tests** — PASS. Proof:
  [`phase2-problem-review-frontend.md`](../../../pwa_tests/reports/phase2-problem-review-frontend.md).
- Phase 2E Staff UI добавляет real-client matching/condition metadata workflow,
  fail-closed publication gate и revision-scoped recovery обоих черновиков из
  `localStorage`. Targeted Storybook — **14 PASS**, Staff production build —
  PASS; snapshots не обновлялись. Proof:
  [`phase2-problem-review-ui.md`](../../../pwa_tests/reports/phase2-problem-review-ui.md).
- Persisted-PDF increment добавляет admin-only descriptor/stream, проверяет
  derivative metadata и exact stored bytes, а в Staff объединяет
  PWA/Telegram/PDF preview без добавления print workflow. Python aiohttp —
  **26 PASS**, frontend unit — **26 PASS**, targeted Storybook — **11 PASS**,
  строгие проверки и Staff production build — PASS. Proof:
  [`phase2-content-pdf-http.md`](../../../pwa_tests/reports/phase2-content-pdf-http.md).
- Bulk-upload target discovery больше не зависит от filename conventions:
  repository/API возвращают только siblings одного `course_lesson`, а strict
  contract/client требуют уникальные public targets. Real aiohttp — **27
  PASS**, frontend unit — **28 PASS**, строгие проверки — PASS. UI orchestration
  закрыта следующим инкрементом. Proof:
  [`phase2-bulk-upload-targets.md`](../../../pwa_tests/reports/phase2-bulk-upload-targets.md).
- Staff bulk-upload UI требует явное file → group lesson → material kind
  сопоставление, валидирует границы и duplicate slots, последовательно
  обрабатывает набор с per-file progress/partial failure и не публикует
  revisions автоматически. Targeted unit — **25 PASS**, Storybook — **12
  PASS**, strict checks и Staff production build — PASS; mobile/desktop light
  просмотрены вручную, snapshots не обновлялись. Proof:
  [`phase2-bulk-upload-ui.md`](../../../pwa_tests/reports/phase2-bulk-upload-ui.md).
- Production-build browser checkpoint `3b5a4e8` добавляет отдельный guarded
  content fixture/seed и `make pwa-e2e-content`. Настоящие Staff и Student UI,
  aiohttp, compiler и SQLite прошли upload → matching → metadata → publish →
  Student read → вторую revision → rollback: **3 PASS** в Chromium, WebKit и
  Firefox. Proof:
  [`phase2-content-e2e.md`](../../../pwa_tests/reports/phase2-content-e2e.md).
- Phase 2 всё ещё открыт для production owner-reviewed parity/backfill и owner
  visual approval. Missing-asset recovery пока не включён в один Playwright
  flow с публикацией и остаётся доказан отдельными live/API/Storybook suites.
  Snapshots не обновлялись. Ранее закрытые HTTP/frontend proof:
  [`phase2-content-api.md`](../../../pwa_tests/reports/phase2-content-api.md),
  [`phase2-content-frontend.md`](../../../pwa_tests/reports/phase2-content-frontend.md).

## Текущий инкремент этапа 3

- Phase 3A revision `d70b0d9` открывает authenticated Student course list и
  enrollment detail поверх revalidated session authority. Handler не принимает
  `studentId`, не выполняет собственный N+1 и возвращает одинаковый `403` для
  неизвестного либо неразрешённого course context.
- `@vmsh/app-shell` экспортирует strict same-origin client и principal-scoped
  TanStack Query hooks. Runtime фиксирует Student audience/API base, unsafe ID
  отклоняется до сети, `401` допускает один штатный refresh/retry.
- Real aiohttp/SQLite auth+content regression — **45 PASS**; app-shell/course
  contracts — **90 PASS**; Ruff, Prettier, ESLint, два strict typecheck и Student
  production build/injectManifest — PASS. Proof:
  [`phase3-course-access-api.md`](../../../pwa_tests/reports/phase3-course-access-api.md).
- Phase 3B revision `66f30c0` добавляет опубликованный lesson list/detail одним
  bounded query; полный content HTTP regression — **32 PASS**, focused TS —
  **16 PASS**. Proof:
  [`phase3-student-lessons-api.md`](../../../pwa_tests/reports/phase3-student-lessons-api.md).
- Phase 3C revision `77927e0` добавляет server-owned home snapshot и подключает
  production `/student/` к реальным enrollment/lesson данным. Production-build
  Staff publish→Student home/read→rollback прошёл **3/3** в Chromium, WebKit и
  Firefox; focused TS — **22 PASS**, content HTTP — **32 PASS**. Proof:
  [`phase3-student-home.md`](../../../pwa_tests/reports/phase3-student-home.md).
- Phase 3D revision `42ea05c` подключает production `/student/tasks` к
  course/group-scoped cursor archive и exact published group lesson. Полный
  regression: **259 TS + 1098 Python PASS**, Storybook **180 PASS**,
  production browser checkpoint **3/3 PASS**. Proof:
  [`phase3-student-task-archive.md`](../../../pwa_tests/reports/phase3-student-task-archive.md).
- Phase 3E revisions `1aeb78d`, `8448a8b` добавляют immutable public identity,
  course/group-scoped canonical problem list, реальные queue/result/synonym
  states и focused condition URL с `problem-*`. Полный regression: **263 TS +
  1100 Python PASS**; production browser checkpoint **3/3 PASS**. Proof:
  [`phase3-student-problem-list.md`](../../../pwa_tests/reports/phase3-student-problem-list.md).
- Phase 3F revision `fabdf93` добавляет точные material availability states,
  закрывает прямой Student hint/solution GET и атомарно пишет immutable reveal
  только после явного подтверждения. Shared disclosure не показывает content
  до успешного audit POST и восстанавливается после ошибки. Полный regression:
  **265 TS + 1100 Python PASS**, Storybook **181 PASS**, production browser
  checkpoint **3/3 PASS**. Proof:
  [`phase3-student-material-reveal.md`](../../../pwa_tests/reports/phase3-student-material-reveal.md).
- Phase 3G revisions `50cd541`, `d4b0b9b`, `89cefb7`, `bb6c6ef`, `d822e2e`
  добавляют secret-free durable auth boundary, 10 MiB owner-scoped validated
  Dexie cache и offline read-through для production Student. Audited hint
  доступен после cold reload, новая publication не доверяет старому reveal, а
  второй Student не видит cache первого. Полный regression: **283 TS + 1101
  Python PASS**, Storybook **182 PASS**, production browser checkpoint **3/3
  PASS**. Proof:
  [`phase3-student-offline-reading.md`](../../../pwa_tests/reports/phase3-student-offline-reading.md).
- Phase 3H revision `f787a64` добавляет browser stress-fixture из четырёх копий
  реальных листков 39–41: **132 задачи / 56 KaTeX**, exact structural checks,
  SVG load-error fallback и мягкий render budget **≤2500 мс**. Полный regression
  — **285 TS + 1101 Python PASS**, Storybook browser — **183 PASS**, strict
  checks и production builds PASS; focused story test time текущего запуска —
  **672 мс**. Proof:
  [`phase3-long-math-rendering.md`](../../../pwa_tests/reports/phase3-long-math-rendering.md).
- Phase 3 остаётся открыт только для ручного visual owner gate; snapshots не
  обновлялись.

## Текущий инкремент этапа 4

- Phase 4A revision `6409191` добавляет additive ledger schema: immutable
  test attempts, idempotency operation и exact checker/config snapshots без
  изменения legacy `results`.
- Phase 4B revisions `bd0487f`, `1d5df54` фиксируют все 23 historical
  `ANS_TYPE`, `strip()` + `fullmatch`, visible-label `SELECT_ONE`, несколько
  правильных ответов, trusted-admin `cor_ans_checker`, client/server cutoff и
  default 3/hour + 6/day rate policy.
- Connection-per-operation repository проверяет account/course/group/content
  authority, исполняет checker вне writer transaction, затем revalidate-ит
  контекст и атомарно пишет attempt + ровно одну legacy `results` строку.
  Exact idempotency replay, mismatch, concurrent race и fault rollback
  проверены отдельными интеграционными тестами.
- Phase 4C revisions `7793d0f`, `0475cd0` добавляют strict Zod request,
  mutation/history response и principal-scoped query keys, а затем
  authenticated POST/GET поверх настоящих cookie, aiohttp и SQLite. Пустая
  история требует текущего access, собственные старые attempts после отзыва
  группы остаются доступны. Новый commit публикует owner-scoped Student
  invalidation, exact replay — нет.
- Phase 4D revisions `6d1909c`, `bab5947`, `5b682d1`, `3d22373` добавляют
  strict same-origin transport, account/problem/revision-scoped local draft и
  immutable Dexie outbox с retry/crash lease/conflict/receipt semantics.
- Phase 4E revisions `a779493`, `6268092`, `9358e76` подключают production
  focused-task route к настоящему input/draft/outbox/history контуру. Отдельный
  production-build Playwright seed позволяет Admin UI выполнить LaTeX upload →
  matching → metadata → publish, после чего Student UI проходит client format
  error без POST, reload draft, online verdict, реальный browser-offline reload
  и exactly-once retry.
- Phase 4F revision `2b00b06` переводит historical Telegram test-answer
  handler и legacy admin recheck на ту же `evaluate_test_answer` policy. Все
  23 `ANS_TYPE`, visible-label `SELECT_ONE`, invalid-format без расхода лимита
  и безопасный broken-checker path закреплены в `make telegram-history-test`:
  **44 PASS**. Telegram по-прежнему пишет в legacy `results`; PWA attempt/
  idempotency ledger не подменяет отсутствие web revision/account context у
  старых bot-задач.
- Phase 4G revisions `e5b83a4`, `0fde237` добавляют preview/apply recheck для
  `pending_configuration`, привязанный к current published revision, и
  production Staff route `/staff/problems/$problemId`. Immutable attempt
  сохраняет исходный ответ, а authoritative outcome/result обновляются
  атомарно; teacher получает `403`, stale revision — `409`, broken checker
  остаётся retryable. Storybook IDs:
  `product-test-answer--recheck-pending`,
  `product-test-answer--recheck-still-pending`,
  `product-test-answer--recheck-conflict`,
  `product-test-answer--recheck-loading`.
- Focused domain/repository — **66 PASS**; repository/real-aiohttp/app-factory
  regression дополнен recheck concurrency/rollback/authority; contracts —
  **94 PASS**; чистый полный Python run — **1180 PASS / 3 intentional skips**;
  frontend unit — **42 файла / 323 PASS**; Storybook browser — **38 файлов /
  187 PASS**; production-build Phase-4 E2E — **6/6 PASS**: два workflow в
  Chromium, WebKit и Firefox; lint, strict typecheck и production build — PASS.
  Proof:
  [`phase4-test-submission-domain-and-repository.md`](../../../pwa_tests/reports/phase4-test-submission-domain-and-repository.md).
- Функциональные критерии Phase 4 закрыты; открыт только ручной visual owner
  gate. Structured Telegram attempt/idempotency persistence остаётся отдельной
  будущей cutover-задачей и не блокирует этап. Staff recheck/configuration-repair
  для PWA ledger закрыт. Product input/recheck stories служат UI-контрактом;
  snapshots не обновлялись.

## Текущий инкремент этапа 5

- Phase 5A revisions `5acecbb`, `c6d6fd8` добавляют migrations
  `0047.pwa_submission_threads_entries_assets`: versioned threads/entries,
  максимум 10 final submission WebP ≤1920, review evidence lock и append-only
  material reassignment без изменения legacy Telegram discussions/queue.
- Condition revision scope проверяется через concrete `problem_revisions`.
  Sparse non-negative attachment ordinal позволяет безопасный reorder при
  immediate SQLite UNIQUE; отдельный trigger обеспечивает продуктовый лимит.
- Exact `up → down → up`, additive row preservation, state/version/owner/result
  scopes, attachment contract/limit/reorder/lock и reassignment audit:
  **6 PASS**. Schema lifecycle regression: **31 PASS**.
- Entry-revision hardening migration `0048` фиксирует exact
  `problem_revision_id` на каждой Student entry; thread остаётся общей историей
  после новой публикации условия, а старый teacher/Telegram backfill может
  оставить поле пустым.
- Fresh inventory: **263 product objects**, SHA-256 `8032fb8b…`; полный
  checkpoint: **323 frontend + 1186 Python PASS**, 3 intentional skips и одна
  существующая SymPy warning. `make pwa-schema-check`, Ruff и
  `git diff --check` — PASS. Proof:
  [`phase5-written-submission-schema.md`](../../../pwa_tests/reports/phase5-written-submission-schema.md).
- Upload/conversion/cleanup, offline composer, backfill,
  reassignment API/UI, Storybook и E2E остаются следующими Phase 5 increments;
  наличие схемы их не доказывает.
- Phase 5B revisions `dbfd1ae`, `acbc8ec` добавляют text-only server vertical:
  connection-per-operation repository, strict Zod fixture/contract и три
  authenticated Student endpoints create/submit/read. Устные типы 3/4 также
  принимают письменный материал; test type 1 остаётся в Phase 4 API.
- Draft→submitted и thread→awaiting_review выполняются атомарно; exact replay и
  ожидаемый failure хранятся в общем idempotency ledger, а неожиданный fault
  откатывает весь unit of work. Closed owner history читается после access
  revoke; чужая/недоступная задача не раскрывается.
- Focused repository — **11 PASS**, общий submission repository — **34 PASS**,
  real aiohttp content/submission — **39 PASS**, written Zod — **4 PASS**.
  Полный checkpoint: frontend **43 файла / 327 PASS**, Python PWA **1199 PASS /
  3 intentional skips / 1 existing SymPy warning**, Storybook browser **38
  файлов / 187 PASS**; lint, strict typecheck и production build с обоими
  injectManifest — PASS. Proof:
  [`phase5-written-submission-api.md`](../../../pwa_tests/reports/phase5-written-submission-api.md).
- Phase 5C revision `9c065db` добавляет bounded multipart photo upload,
  shared raster/HEIC→WebP converter, server-derived `sol_imgs` key, final
  storage metadata и owner-only integrity-checked media read. Source image не
  становится durable object; final WebP обязан иметь обе стороны ≤1920.
- Object put предшествует одной SQLite transaction. Stale/mismatch/fault после
  put удаляет уникальный object; concurrent exact replay не оставляет объект
  проигравшего запроса. `written-attachment:create` replay останавливается до
  повторной конвертации и storage write.
- Focused attachment/service/repository — **10 PASS**, общий submission
  repository — **44 PASS**, real aiohttp content/submission — **40 PASS**,
  written Zod — **5 PASS**. Полный checkpoint: frontend **43 файла / 328
  PASS**, Python PWA **1210 PASS / 3 intentional skips / 1 existing SymPy
  warning**, Storybook browser **38 файлов / 187 PASS**; lint, strict typecheck
  и production build с обоими injectManifest — PASS. Proof:
  [`phase5-written-attachment-api.md`](../../../pwa_tests/reports/phase5-written-attachment-api.md).
- Phase 5D revision `38579a5` добавляет complete-list reorder, logical delete
  и explicit no-op response для draft и submitted-before-review evidence.
  SQLite migration `0049` запрещает оставить submitted entry без текста и
  фотографий; owner/version/state/lock повторно проверяются в одной write
  transaction.
- Reorder использует временные sparse ordinals и заканчивает плотным `0…n-1`.
  Delete сразу удаляет attachment из projection и ставит asset `deleted_at`;
  physical final WebP остаётся под принятой admin-managed retention policy.
  Locked evidence возвращает отдельный conflict, exact replay не меняет версии
  и не публикует повторную invalidation.
- Repository/schema/real-aiohttp checkpoint — **88 PASS**, written Zod — **6
  PASS**, schema inventory — **264 objects / PASS**. Полный checkpoint:
  frontend **43 файла / 329 PASS**, Python PWA **1215 PASS / 3 intentional
  skips / 1 existing SymPy warning**, Storybook browser **38 файлов / 187
  PASS**; lint, strict typecheck и production build с обоими injectManifest —
  PASS. Proof:
  [`phase5-written-attachment-mutations.md`](../../../pwa_tests/reports/phase5-written-attachment-mutations.md).
- Phase 5E infrastructure revision `d3b29f2` добавляет bounded one-shot image worker и
  `localStorage`/Dexie written draft: текст, порядок, revision и resumable server
  IDs переживают reload, owner/runtime/revision изолированы, а binary orphans и
  quota failure имеют явное восстановление. Client WebP ограничен 1920 px;
  source остаётся только для server fallback. Focused suite — **28 PASS**;
  исходный infrastructure checkpoint: frontend **45 файлов / 344 PASS**,
  Python PWA **1215 PASS / 3 intentional skips / 1 existing SymPy warning**.
- Phase 5F revisions `4e835ec`, `2158398` подключают canonical Student
  composer к настоящему written/oral task route и durable create → upload →
  optional reorder → submit outbox. Preview, порядок, максимум 10 страниц,
  freeze queued evidence, resume после reconnect и очистка только после receipt
  теперь исполняются production-кодом, а не только infrastructure tests.
- Реальный WebKit выявил `UnknownError` при записи Blob/File в IndexedDB;
  бинарный durable format заменён на portable `ArrayBuffer` с read-only legacy
  Blob compatibility. Одна страница не создаёт лишний reorder request.
- Актуальный checkpoint: `make pwa-lint`, `make pwa-typecheck`, `make pwa-build`
  — PASS; frontend unit — **47 файлов / 359 PASS**; Python PWA — **1215 PASS /
  3 intentional skips / 1 existing SymPy warning**; Storybook browser — **38
  файлов / 188 PASS**. Story `product-submission--queued` проверяет frozen
  queued state с addon-a11y `error`.
- Production-build E2E с настоящими aiohttp, seeded SQLite и filesystem media
  adapter — **3/3 PASS** в Chromium, WebKit и Firefox: фото переживает reload,
  offline enqueue не пишет в сеть, reconnect делает ровно один create/upload/
  submit и сервер хранит submitted WebP evidence. E2E gateway abort regression
  — **17 PASS**.
- Revision `71e96e6` добавляет отдельный guarded
  `make pwa-written-attachment-live-smoke`. Run
  `phase5-written-service-20260728-b2` подтвердил настоящий
  WrittenAttachmentService → raster converter → test S3 путь: `sol_imgs` key,
  final WebP, private read, public GET и delete acknowledgement — PASS. Общий
  run `phase5-written-20260728-a2` тем же bucket проверил также TikZ→SVG.
  Focused storage/service/harness regression — **86 PASS**. Proof:
  [`phase5-written-storage-live.md`](../../../pwa_tests/reports/phase5-written-storage-live.md).
- Объединённый proof:
  [`phase5-written-browser-draft.md`](../../../pwa_tests/reports/phase5-written-browser-draft.md).
- Phase 5G revisions `1fa320b`, `6b30141`, `9d3b821`, `34d371d` добавляют
  append-only `submission_entry_replacements`, атомарный Student API и durable
  local replacement intent. Прежняя entry/evidence остаётся отдельно и
  становится `deleted` только вместе с переводом новой entry в `submitted`.
- Replacement draft копирует прежний текст и authenticated WebP, переживает
  reload и завершает resumable create/upload цепочку вызовом `replace` вместо
  `submit`. Reconnect race закрыт; retry backoff возрастает до 30 секунд.
- Focused frontend — **4 файла / 32 PASS**; актуальный frontend checkpoint —
  **47 файлов / 362 PASS**; schema inventory — **269 objects / 21 focused
  PASS**; полный Python PWA — **1223 PASS / 3 intentional skips**; Storybook —
  **38 файлов / 188 PASS**. Production-build submissions E2E — **9/9 PASS**,
  включая replacement в Chromium, WebKit и Firefox. Proof:
  [`phase5-written-replacement.md`](../../../pwa_tests/reports/phase5-written-replacement.md).
- Phase 5H revision `0e8b84f` реализует Staff preview и append-only перенос
  выбранного текста/фотографий между конкретными задачами одного школьника.
  Физические entry/attachment/object/result/verdict остаются в исходной ветке;
  Student получает target projection с provenance и две owner invalidations.
- Focused contracts/repository/aiohttp — **8 + 3 + 1 PASS**; broad written
  regression — **27 PASS**. Актуальный полный checkpoint: frontend **47 файлов /
  363 PASS**, Python PWA **1227 PASS / 3 intentional skips**, lint/typecheck и
  production build — PASS. Proof:
  [`phase5-written-material-reassignment.md`](../../../pwa_tests/reports/phase5-written-material-reassignment.md).
- Phase 5I revisions `08ac0bf`, `89d0427`, `a2187c7`, `4d7b4f6` закрывают
  authenticated Staff WebP media route, typed preview/commit/media client и
  reusable correction UI. Storybook IDs:
  `product-review--material-reassignment` и
  `product-review--material-reassignment-post-review`; desktop/mobile-light
  просмотрены вручную, найденный mobile overflow исправлен, snapshots не
  обновлялись. Актуальный checkpoint: frontend **48 файлов / 367 PASS**,
  Python PWA **1227 PASS / 3 intentional skips / 1 existing SymPy warning**,
  Storybook browser **39 файлов / 190 PASS**, lint/typecheck/production build —
  PASS. Proof:
  [`phase5-written-material-reassignment.md`](../../../pwa_tests/reports/phase5-written-material-reassignment.md).
- Следующие gates: legacy backfill и visual owner approval. Production review
  route/search wiring, полный Staff review и media corpus закрыты последующими
  инкрементами.
- Phase 6A revision `16980f6` rebuild-ит `written_tasks_queue`, исправляет
  affinity `teacher_id`, добавляет opaque ID и renewable lease. Shared-SQLite
  repository захватывает все ветки одного Student+modern-synonym-case,
  fail-closed проверяет Staff scope, уважает живой 30-минутный Telegram lock и
  даёт ровно одного победителя при concurrent claim. Focused queue/migration/
  legacy — **10 PASS**; schema inventory — **274 objects / 31 PASS**;
  seed/maintenance — **117 PASS**; полный checkpoint — **367 frontend + 1233
  Python PASS / 3 intentional skips / 1 existing SymPy warning**. Proof:
  [`phase6-review-queue-leases.md`](../../../pwa_tests/reports/phase6-review-queue-leases.md).
- Phase 6B revisions `8742244`, `b2c539c` добавляют authenticated Staff
  list/claim/heartbeat/release, public course/group scope без частичной утечки
  synonym-case, strict wire contracts и account-scoped browser client. Focused
  Python — **8 PASS**, TypeScript — **2 файла / 9 PASS**; полный checkpoint:
  frontend **50 файлов / 376 PASS**, Python PWA **1237 PASS / 3 intentional
  skips / 1 existing SymPy warning**, lint/typecheck/production build — PASS.
  Proof:
  [`phase6-review-queue-http.md`](../../../pwa_tests/reports/phase6-review-queue-http.md).
- Phase 6C revisions `7c52472`, `30c9f11`, `7df0d81` добавляют append-only
  review/evidence schema, exact multi-branch snapshot, atomic target-last
  result/comment/queue transaction, evidence freeze, idempotent replay,
  authenticated complete endpoint, strict TypeScript client и owner-scoped
  invalidation. Focused Python/HTTP — **12 PASS**, focused TypeScript — **12
  PASS**; полный checkpoint: frontend **50 файлов / 379 PASS**, Python PWA
  **1241 PASS / 3 intentional skips / 1 existing SymPy warning**, schema **298
  objects**, lint/typecheck/production build — PASS. Proof:
  [`phase6-review-completion.md`](../../../pwa_tests/reports/phase6-review-completion.md).
- Phase 6D revisions `9fdfe98`, `b93defa` добавляют versioned normalized
  annotation manifest для exact reviewed attachment, все core marks и optional
  highlight, rotation, strict geometry/size limits, atomic/idempotent storage и
  strict HTTP/Zod transport. Focused Python/HTTP — **19 PASS**, focused
  TypeScript — **12 PASS**; полный checkpoint: frontend **50 файлов / 379
  PASS**, Python PWA **1248 PASS / 3 intentional skips / 1 existing SymPy
  warning**, Storybook **39 файлов / 190 PASS**, schema **303 objects**,
  lint/typecheck/production build — PASS. Proof:
  [`phase6-review-annotations.md`](../../../pwa_tests/reports/phase6-review-annotations.md).
- Phase 6E revisions `1db6f0b`, `978d0e9` добавляют current internal Teacher
  reaction и append-only history, атомарную initial reaction, часовое окно,
  optimistic set/delete/reselect, original-reviewer/scope authorization и
  strict HTTP/Zod/Staff-client transport. Focused migration/repository/schema —
  **39 PASS**, real aiohttp — **6 PASS**, focused TypeScript — **14 PASS**;
  полный checkpoint: frontend **50 файлов / 381 PASS**, Python PWA **1254 PASS /
  3 intentional skips / 1 existing SymPy warning**, Storybook **39 файлов / 190
  PASS**, schema **312 objects**, lint/typecheck/production build — PASS. Proof:
  [`phase6-review-internal-reactions.md`](../../../pwa_tests/reports/phase6-review-internal-reactions.md).

## Текущий инкремент этапа 1

- `4343371` добавляет чистые правила входа, Argon2id, вычисление ближайшей
  границы 10 августа по Москве, HMAC refresh digest и audience-salted signed
  access token; `08d6980` приводит публичный session ID к каноническому
  lowercase browser-контракту. Focused Python suite: 24 PASS.
- `3b22eaa` добавляет fail-closed auth runtime config: отдельные public origins,
  cookie names/paths, signing keyring и независимые refresh/throttle peppers.
  Prototype defaults существуют только для известных isolated profiles;
  production не смешивается с ними. Auth/config suite: 36 PASS.
- `36f6bb2` добавляет Zod-first audience-specific login/auth/session и
  multi-course enrollment/access contracts, versioned synthetic valid/invalid
  fixtures и principal-scoped query keys. Student body не принимает `audience`,
  а срок fixture `2026-08-09T21:00:00Z` явно доказывает московскую границу.
  Focused Vitest: 15 PASS; contracts typecheck, ESLint и Prettier PASS.
- Cookie/token boundary принимает только тот же 32-символьный lowercase hex
  session reference, который создаёт генератор и принимает repository. Даже
  корректно подписанный payload с неканоническим `sid` отклоняется до SQLite;
  focused model suite — 29 PASS.
- Чистые permission и request-security policies добавлены в
  `helpers/pwa/{permissions,request_security}.py`: роли и scopes fail-closed,
  Student/Family ownership не смешивается с request scope, Staff collection
  требует scope-filtered repository query, а unsafe login проходит тот же
  Origin/Referer/Fetch Metadata gate. Cookie-bearing WebSocket GET отдельно
  требует allowlisted Origin. Focused suite на этом срезе — 156 PASS; actual
  aiohttp TCP/Unix и nginx structural boundary закрыты более поздним proxy
  increment ниже, server syntax/live burst остаются deploy proof.
- Миграции `0039`/`0040` добавляют auth/session/throttle и первый
  course/enrollment/access/scope слой без изменения legacy IDs и имеют точный
  rollback. Fresh inventory содержит 94 product objects; read-only live report
  честно фиксирует, что `db/vmsh.db` пока отстаёт на две миграции. Phase-1
  актуальный объединённый migration/schema/seed suite — 129 PASS, полный
  Python PWA suite до opaque user-ID increment — 520 PASS / 1 intentional
  skip; полный suite будет повторён после сборки auth repository.
- `baseline-v1` schemaVersion 2 детерминированно материализует Student online,
  Student in-person, Family с двумя детьми, Teacher/Admin, один season/course,
  enrollments/access/scopes и ни одной предварительно созданной browser session.
  Два agent seed запуска дали одинаковый digest `782b4051…`; актуальный
  seed+migration/schema suite — 129 PASS.
- Auth repository реализует connection-per-operation login/session/refresh,
  soft revoke, credential invalidation, shared-worker throttle и
  course/family/staff authority reads. Независимое ревью закрыло exact legacy
  types, identity TOCTOU, Student token↔hash atomicity, canonical public IDs,
  session metadata bounds и collision rollback. Полный Python PWA suite после
  исправлений — 669 PASS / 1 intentional skip; focused auth/schema/seed —
  160 PASS, Ruff/schema/live-drift checks — PASS.
- HTTP auth increment реализует семь audience routes, default-private
  middleware, exact Origin/target boundary, audience cookie paths и
  authoritative SQLite revalidation. Real aiohttp/migrated-SQLite tests
  покрывают Student/Family/Staff login, capabilities, refresh replay, logout,
  logout-all и revoke-device; corrupt-principal cleanup покрыт service tests.
  Focused auth/repository/HTTP/transport gate — 245 PASS; полный `pwa_tests` —
  714 PASS / 1 intentional skip. Logout гарантированно отзывает живую
  access-сессию даже без refresh-cookie, а public allowlist сопоставляет точные
  method/resource пары. Production marker tests доказывают, что
  `pwa-production` и `PROD=true` включают HTTPS/`Secure`, а prototype
  fail-closed запрещён.
- Authenticated realtime increment связывает каждый WebSocket с проверенными
  audience/account/session до upgrade, сериализует все операции над transport,
  закрывает session/account sockets local-first и через строгий versioned NATS
  control event, а при сбое fan-out fail-closed перепроверяет server state в
  SQLite. Owner-scoped invalidation доставляется только вкладкам нужного
  account и не раскрывает account ID в browser payload или логах. Logout,
  refresh-only logout, revoke-device и logout-all закрывают только доказанные
  targets; wrong/foreign/replayed refresh secret не образует close-oracle.
  Полный `.venv/bin/pytest -q pwa_tests` — 759 PASS / 1 intentional skip;
  missing/wrong Origin, cross-audience cookie, expired/out-of-band-revoked
  session, multiple tabs/devices, cross-worker close, publish failure fallback,
  send/close race и owner isolation покрыты регрессиями.
- Phase-1 race/resource hardening делает post-upgrade socket pending и
  non-routable до повторной SQLite-проверки и первого cursor frame. Session
  tombstone закрывает auth→register revoke race, а audience broadcast lock —
  initial-frame/invalidation ordering. Stored Argon2id дополнительно проходит
  generous bounded resource policy; malformed/out-of-policy active row и
  unknown login выполняют один и тот же dummy verify. Barrier/work-count tests
  не используют wall-clock. Focused suites — 31 PASS и 45 PASS; полный
  `.venv/bin/pytest -q -n0 pwa_tests` — **808 PASS / 1 intentional skip**.
  Proof: [`phase1-auth-race-hardening.md`](../../../pwa_tests/reports/phase1-auth-race-hardening.md).
- Frontend auth wiring подключает server-authoritative `/auth/me` во всех трёх
  приложениях после validated runtime (и после IndexedDB gate в Student/Family),
  не монтирует private shell до подтверждённой сессии и сохраняет безопасный
  app-relative `returnTo` с query/hash. Controlled формы используют ровно
  `telegramToken` для Student и `password` для Family/Staff; состояния invalid,
  rate-limited, account-unavailable и network покрыты без account enumeration.
  Явные Staff capability gates закрывают classrooms, broadcasts и audit.
  Route generation, typecheck, ESLint/stylelint и production build трёх apps —
  PASS; Vitest unit — 16 файлов / 138 PASS, Storybook browser mode — 32 файла /
  140 PASS. Реальный browser E2E входа/refresh/logout с aiohttp остаётся gate.
- Domain-neutral session/device UI добавлен в `packages/app-shell` и подключён
  к Student/Family profile: настоящий `GET /auth/sessions`, current marker,
  revoke одной чужой сессии, current logout и logout-all с подтверждением.
  Empty/corrupt/cross-audience ответы и ошибка offline-work inspection работают
  fail-closed; opaque session IDs не становятся видимыми device labels.
  `SessionOfflineWorkGuard` доказывает предупреждение для непустой очереди и
  порядок server logout → cleanup даже при размонтировании shell, но реальный
  Dexie adapter честно отложен. Staff route не придуман. Focused unit — 18
  PASS; session Storybook interaction + addon-a11y — 9 PASS; snapshots не
  обновлялись и visual owner gate остаётся открытым.
- Frontend auth hardening сериализует single-use refresh между вкладками через
  audience-scoped Web Locks. Каждый получивший lock сначала повторяет `/auth/me`;
  поэтому второй contender не расходует уже ротированный secret. Без Web Locks
  bounded BroadcastChannel/storage wake-up приводит только к fail-closed
  `/auth/me`, а не к небезопасной localStorage-lease. `sessionExpiresAt`
  enforced как абсолютная server-owned граница таймером и browser-resume
  checks; prior-verified `offline-unverified` UI размонтируется по expiry.
  Focused auth/session Vitest — 31/31 PASS, app-shell typecheck и scoped ESLint
  — PASS. Повторный полный gate: frontend unit 19 файлов / 162 PASS, Python PWA
  808 PASS / 1 intentional skip, Storybook browser mode 33 файла / 152 PASS;
  full lint/typecheck — PASS.
- Canonical auth preflight теперь исполняет frozen Student username algorithm
  v1 на read-only snapshot `db/vmsh.db`: 1617 Student rows, 10 field/token
  blockers, 29 collision groups / 58 affected rows и 1549 eligible до явных
  overrides/launch-cohort exclusions. Отчёты не содержат IDs, login candidates
  или credentials; focused privacy/source-safety suite — 10 PASS. Apply и
  collision overrides ещё не выполнены.
- Controlled Student import tooling готово для **отдельной migrated copy**:
  owner-only inventory, deterministic preview без Argon2 и all-at-once apply с
  повторной проверкой под `BEGIN IMMEDIATE`. Explicit cohort/exclusions и
  overrides обязательны; target разрешён только под `.runtime/auth-import/`, а
  authoritative/human/agent DB, symlink/hardlink, небезопасные
  permissions и несовпавший confirmation path отклоняются. Повторный apply
  идемпотентен, а aggregate proof не содержит IDs/login candidates/credentials.
  Quiescent snapshot sidecars также fail-closed. Focused suite — 16 PASS,
  включая concurrent source change; synthetic 1617-row
  preview — менее `1 s`, без Argon2; локальная оценка default Argon2 для 1549
  pending rows — около `0.8 min` до write transaction и ещё `0.8 min` для
  post-commit verification. Runbook:
  [`phase-1-student-auth-import.md`](../../docs/phase-1-student-auth-import.md),
  proof: [`phase1-auth-import-tooling.md`](../../../pwa_tests/reports/phase1-auth-import-tooling.md).
  Настоящие overrides/exclusions и production apply не выполнялись; course
  enrollment/access/event backfill явно отложен и не фабрикует `G`/`O` events.
- Production proxy boundary реализован: one-host nginx template, exact
  forwarding replacement, per-IP login `429`/`Retry-After`, fail-closed CSP,
  loopback TCP/exact Unix transport и wrong-path/host/proto/chain/WS Origin
  regression. Production hostname не зашит: checker требует exact approved
  lowercase `VMSH_PWA_PUBLIC_HOST` и сверяет оба `server_name`, redirect и CSP.
  Pure + actual aiohttp + structural suite — 106 PASS; локальный
  syntax helper вернул explicit `UNAVAILABLE`/exit 2 из-за отсутствующего nginx;
  полный Python PWA suite — 793 PASS / 1 intentional skip.
- Следующий gate: server `nginx -t` и live rate-limit smoke, утверждённые
  owner decisions + rehearsal/apply controlled import
  и реальный browser E2E login/refresh/logout/revoke. Владелец принял
  риск старых credential-like literals в migration history; они не копируются
  в fixtures/reports и не становятся источником нового web-входа. Controlled
  production activation всё равно требует preflight, актуальных
  Telegram-токенов и явного отчёта. Позднее owner-решение заменило этот
  legacy-backfill как основной onboarding: target Student batch получает login
  явно и предлагает `-NN` при конфликте; inventory остаётся compatibility
  rehearsal, а не блокером MVP.

## Phase 1 browser-auth increment — 27 июля 2026

- Production entry всех трёх приложений использует server-authoritative auth;
  private routes сохраняют безопасный intended route с query/hash, а Teacher и
  Admin получают разные Staff route gates.
- Единый test-only fixture
  `pwa_tests/fixtures/auth-credentials-v1.json` согласован с seed; product bundle
  его не импортирует. Playwright использует настоящий aiohttp и отдельную SQLite
  через one-origin gateway, без MSW, Telegram, Google и mock-auth backdoor.
- `make pwa-e2e-auth` — **60/60 PASS** в Chromium, WebKit и Firefox: четыре
  роли, reload/logout, cookie Path и audience isolation, simultaneous sessions,
  invalid credentials, deep-link return, `401`, Host/Origin/forwarding,
  explicit refresh rotation, single-flight automatic recovery при отсутствующей
  access-cookie, two-tab recovery с ровно одним refresh request и revoke
  отдельного устройства.
- Этот production-build gate повторно подтверждён 28 июля после исправления
  default deep-link; отдельный Phase-2 content Playwright flow позднее закрыт
  revision `3b5a4e8`.
- Browser proof нашёл и закрыл Family `500` на ISO `users.birthday`:
  `FamilyChildRecord.birthday` читает nullable строку; repository regression
  закрепляет реальный формат legacy данных.
- Актуальные соседние gates: Vitest **16 файлов / 139 PASS**; Python PWA
  **780 PASS / 1 intentional skip**; Storybook browser mode **32 файла / 143
  PASS** с addon-a11y error; lint, typecheck и production build — PASS.
- Более ранние строки этого журнала, где browser auth E2E назван будущим gate,
  этим блоком заменены. Не закрыты controlled production import, server
  `nginx -t`/live rate smoke и browser Teacher→admin API `403`: последний ждёт
  первого настоящего capability-protected admin endpoint Phase 2/7/8/10.
  Искусственный production endpoint ради теста не добавляется; UI forbidden и
  permission/API matrix уже покрыты.

## Phase 1 frontend realtime increment — 27 июля 2026

- Общий [`RealtimeProvider`](../../packages/app-shell/src/realtime.tsx)
  подключён в production entry Student, Family и Staff только внутри
  authenticated context. Same-origin URL содержит максимум memory cursor;
  credential/account/session IDs не попадают в URL или Web Storage.
- Клиент fail-closed валидирует frame, требует `connected` на первом handshake
  и `resync-required` после любого reconnect, выполняет полный active Query
  refetch до ready, коалесцирует invalidations и ограничивает
  handshake/heartbeat/backoff. Offline/hidden и StrictMode cleanup не оставляют
  reconnect storm или дублирующий transport.
- `1008` и нормализованный transport-слоем `1000` запускают HTTP authority
  check. Revoke current session переводит private route на login и не открывает
  новый socket; подтверждённая session продолжает обычный cursor/refetch path,
  transient network/5xx повторяет authority check с bounded backoff и не
  оставляет клиент навсегда заблокированным.
- Focused Vitest: **2 файла / 17 PASS**. `make pwa-e2e-realtime`: **12/12 PASS**
  в Chromium, WebKit и Firefox после production build трёх приложений.
  Visual snapshots не обновлялись; provider не меняет визуальное состояние.
- Повторный полный `make pwa-e2e-runtime` сначала подтвердил realtime revoke /
  reconnect, theme-storage и IndexedDB isolation, но обнаружил шесть падений
  Student/Family PWA-update. Разбор trace показал, что новый worker уже
  становился controller и приложение делало reload, а тест ошибочно требовал
  навигацию на корневой URL: к этому моменту auth boundary мог сохранить
  `/student/login?returnTo=…` или `/family/login?returnTo=…`. Product-кнопка
  теперь адресует фактический `registration.waiting` напрямую, а E2E доказывает
  reload с сохранением текущего audience-local URL. Точный повторный сценарий
  `a byte-different built worker reaches prompt and controls the page` —
  **6/6 PASS** в Chromium, WebKit и Firefox. Полный runtime suite после этой
  локальной правки ещё должен быть повторён; snapshots не обновлялись.
- Реализующие/проверяющие файлы:
  [`realtime-client.test.ts`](../../packages/app-shell/src/realtime-client.test.ts),
  [`realtime-provider.test.tsx`](../../packages/app-shell/src/realtime-provider.test.tsx),
  [`runtime-isolation.spec.ts`](../../e2e/runtime-isolation.spec.ts),
  [`e2e_runner.py`](../../scripts/e2e_runner.py). Target зафиксирован как
  `make pwa-e2e-realtime`.

## Phase 2 browser content renderer increment — 27 июля 2026

- Production browser wire отделён от внутреннего compiler AST и legacy
  `web_html`: [`WebContentDocument v1`](../../packages/contracts/src/content.ts)
  имеет tagged camelCase blocks, один material kind, обязательный persisted
  `revisionId` и отдельную nullable preview schema. Generic preflight до
  recursive Zod parsing ограничивает depth/nodes/text; shared Python preview
  fixture доказывает отсутствие sibling answer/hint/solution branches.
- [`SemanticMathDocument`](../../packages/content/src/math-document.tsx)
  рендерит paragraphs/headings/lists/subparts/callouts/tables/formulas и только
  внешние SVG/raster figures. Compatibility `MathHtml` fail-closed отклоняет
  script/event/style/inline SVG/forms/unsafe URL целиком и монтирует очищенный
  `DocumentFragment`, не raw HTML string.
- KaTeX работает на клиенте с `trust:false`, bounded `maxSize`/`maxExpand` и
  детерминированным локальным fallback. [`ZoomableAssetFigure`](../../packages/content/src/zoomable-asset-figure.tsx)
  применяет один transform к холсту и изображению, поддерживает keyboard,
  buttons, pinch/pan и missing/load-error state.
- Focused Zod/sanitizer/renderer unit: **3 files / 33 PASS**; TypeScript,
  scoped ESLint/stylelint и `git diff --check` — PASS. Focused Storybook
  browser mode: **9/9 PASS** в Chromium с addon-a11y `error`. Story IDs и
  остающиеся integration/visual gates: [`phase2-web-renderer.md`](../../../pwa_tests/reports/phase2-web-renderer.md).
- Этап 2 целиком не закрыт: API/page wiring, storage/asset resolution,
  publication flow, corpus/PDF/Telegram/S3 gates и visual owner approval ещё
  впереди. Snapshots не обновлялись.

## Phase 2 live derivatives и authenticated content vertical — 28 июля 2026

- Локальный полный TeX дал воспроизводимую PDF-производную: real
  `pdflatex` smoke — **1 PASS**. Test bot в подтверждённом приватном test
  channel выполнил compiler-owned Rich Message на границе 32 768 symbols:
  send/edit/delete/cleanup — **PASS**, публикация удалена. Proof:
  [`phase2-derivative-adapters.md`](../../../pwa_tests/reports/phase2-derivative-adapters.md).
- Фиксированные synthetic TikZ и raster прошли реальный
  SVG/WebP → test S3 `PutObject` → private read → public GET → delete под
  `integration/phase2-assets-20260727-a1/`: **2/2 PASS**, оба объекта удалены.
  Hermetic service/guard suite — **13 PASS**. Proof:
  [`phase2-content-assets-live.md`](../../../pwa_tests/reports/phase2-content-assets-live.md).
- Повторное review после `0042`/`0043` приняло backend boundary в `1aad776`:
  source/compile leases и publication slots сериализованы, rollback отменяет
  ровно ожидаемый schedule, due scheduler/hide/invalidation и terminal audit
  проверены. Publish/schedule/rollback дополнительно требуют resolved problem
  matches + reviewed metadata; solution требует отдельный lesson cutoff.
  Staff history ограничена сервером и содержит authoritative timezone.
- Frontend vertical в `866e3fe` использует тот же wire: после reload продолжает
  `uploaded`/expired-compiling revision, для rollback предлагает предыдущую
  `ready`, не переводит `datetime-local` через timezone браузера, подтверждает
  publish/schedule/rollback/hide и показывает два preview рядом на desktop.
  Student/Family читают только published typed document и отмечают новую
  revision без показа внутренних compiler/publication данных.
- Полный общий gate: lint/typecheck/build/schema PASS, 218 TypeScript unit,
  1028 Python PASS (3 skip, 1 warning), 167 Storybook browser PASS и 192
  product schema objects. Подробные команды и остающиеся границы:
  [`phase2-content-api.md`](../../../pwa_tests/reports/phase2-content-api.md) и
  [`phase2-content-frontend.md`](../../../pwa_tests/reports/phase2-content-frontend.md).
- Этот checkpoint сам по себе не завершал Phase 2: перечисленные здесь asset,
  matching/metadata, stored PDF, bulk-upload и production content E2E gaps
  закрыты последующими proof выше. Текущие открытые gate — production
  owner-reviewed parity/backfill и owner visual approval. Snapshots не
  обновлялись.

## Phase 2 real-content Storybook gate — 27 июля 2026

- Условия начинающих занятий 39–41 теперь имеют воспроизводимые committed
  fixtures: exact source/PDF SHA-256, typed PWA document и Telegram Rich
  derivative из одного compiler run. Stale fixture обнаруживает отдельный
  `check`-режим; Python corpus/renderer suite — **37 PASS**, TypeScript contract
  — **21 PASS**.
- Story
  `Product/Mathematical document/Real corpus--Lessons 39–41 · PWA, Telegram and PDF`
  прошла **1/1** в browser mode с addon-a11y `error`. Desktop и mobile 390 px
  light просмотрены вручную; mobile horizontal overflow отсутствует.
- Visual gate нашёл и закрыл не фиктивную ошибку: print-header newlines больше
  не становятся высоким пустым `<p><br/>…</p>` в Telegram derivative. PDF tab
  показывает проверяемый repository reference artifact, а не browser print.
- Proof:
  [`phase2-real-content-corpus.md`](../../../pwa_tests/reports/phase2-real-content-corpus.md).
  Snapshots не обновлялись, owner visual approval и generated-PDF parity всё
  ещё не закрыты.

## Phase 4 browser transport, production UI, Staff recheck, E2E и Telegram — 28 июля 2026

- [`submission-client.ts`](../../packages/app-shell/src/submission-client.ts)
  добавляет strict same-origin Student transport и TanStack Query hooks;
  единственный `401` retry повторяет тот же body и UUID.
- POST-контракт теперь обязательно несёт expected condition revision/config
  version. Реальный aiohttp отклоняет stale offline payload как
  `409 test_problem_revision_changed`; focused Python integration — **21 PASS**.
- [`test-answer-draft.ts`](../../packages/offline/src/test-answer-draft.ts)
  сохраняет account/problem/revision-scoped текст в `localStorage`, явно
  возвращает несовместимую revision и не скрывает write/quota failure.
- [`test-answer-outbox.ts`](../../packages/offline/src/test-answer-outbox.ts)
  сохраняет immutable request/UUID/hash в Dexie, сериализует claim, повторяет
  network failure и crashed sending lease, удерживает conflict/failed и
  удаляет synced запись только после явного acknowledge.
- Offline focused — **7 файлов / 34 PASS**; полный frontend unit — **39 файлов /
  311 PASS**; TypeScript и scoped ESLint — PASS. Подробный proof:
  [`phase4-test-submission-domain-and-repository.md`](../../../pwa_tests/reports/phase4-test-submission-domain-and-repository.md).
- Revisions `a779493`, `6268092` подключают type-safe input и production
  Student route к transport + draft + outbox + history. Revision `9358e76`
  добавляет отдельный E2E seed/runner target и настоящий offline browser proof.
- Актуальный полный checkpoint: frontend **42 файла / 323 PASS**, Python PWA
  **1180 PASS / 3 intentional skips**, Storybook browser **38 файлов / 187
  PASS**, production-build E2E **6/6 PASS**: Student submit и Staff repair/
  recheck в Chromium, WebKit и Firefox; lint/typecheck/build PASS. MSW,
  Telegram, Google, S3 и `db/vmsh.db` не использовались.
- Revision `2b00b06`: Telegram test-answer handler и legacy admin recheck
  используют общую PWA domain policy; historical fake-Bot/isolated-SQLite
  regression — **44 PASS**, без Telegram network/credentials. Сломанный checker
  не создаёт ложный минус и не раскрывает source/answer/traceback.
- Revisions `e5b83a4`, `0fde237` закрывают Staff configuration repair/recheck
  для нового attempt ledger: current-revision preview/apply, immutable исходная
  попытка, atomic result projection, authority/conflict/concurrency/rollback и
  owner invalidation проверены repository, aiohttp и production-browser tests.
- Открыты ручной visual owner gate и отдельное решение по cutover legacy
  Telegram `results` в structured attempt ledger; snapshots не обновлялись.

## Историческая проверка многокурсового прототипа

Проверено 26 июля 2026 года до Phase 0 runtime-hardening; числовые результаты
этого среза не являются текущим gate, актуальные результаты приведены выше:

- `make pwa-lint`, `make pwa-typecheck`, `make pwa-test`, `make pwa-storybook-test`, `make pwa-build` — успешно;
- unit: 4 файла / 29 тестов; Python PWA: 11 тестов; Storybook browser mode: 31 файл / 137 тестов с `addon-a11y` в режиме error;
- production build всех трёх приложений и отдельный Storybook build — успешно; Student/Family собрали валидные `injectManifest` service workers;
- локальные ссылки проверены в 48 Markdown-файлах; `git diff --check` — успешно;
- вручную в agent Storybook просмотрены mobile-light Student/Family и desktop Staff/course/synonym/progress/classroom stories из [карты design→implementation](18-design-implementation-map.md);
- production visual без обновления snapshots: Staff baseline совпал в Chromium/WebKit/Firefox; Student current week ожидаемо отличается во всех трёх браузерах (1188→1615 px, около 4% пикселей) из-за новой многокурсовой композиции;
- visual snapshots намеренно не обновлены до решения владельца;
- backend endpoints, migrations и production wiring не реализованы и не считаются proof завершения фаз 1–11.

## Фактические proof этапов

Таблица различает промежуточный проверенный инкремент и окончательное принятие
этапа. Наличие revision/proof не закрывает оставшиеся criteria из phase-файла.

| Этап | Revision             | Proof                                                                                                                                                | Принято                                                                                                                  |
| ---: | -------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------ |
|    0 | —                    | —                                                                                                                                                    | —                                                                                                                        |
|    1 | `1aad776`, `866e3fe` | [Этап 1](05-phase-1-auth.md#пруфы-завершения-этапа)                                                                                                  | частично; production gates открыты                                                                                       |
|    2 | `43b0323`…`3b5a4e8`  | [Этап 2](06-phase-2-content.md#пруфы-завершения-этапа)                                                                                               | Browser path принят; этап открыт                                                                                         |
|    3 | `d70b0d9`…`f787a64`  | [Этап 3](07-phase-3-student-reading.md#пруфы-завершения-этапа)                                                                                       | Phase 3A–3H приняты; visual открыт                                                                                       |
|    4 | `6409191`…`0fde237`  | [Phase 4A–4G proof](../../../pwa_tests/reports/phase4-test-submission-domain-and-repository.md)                                                      | функционально; visual открыт                                                                                             |
|    5 | `5acecbb`…`4d7b4f6`  | [Phase 5A–5I proof](../../../pwa_tests/reports/phase5-written-material-reassignment.md)                                                              | browser, test-S3, replacement, reassignment и reusable Staff correction UI приняты; прочие gates открыты                 |
|    6 | `16980f6`…`892646f`  | [Phase 6U Student/Staff support pages](../../../pwa_tests/reports/phase6-support-pages.md)                                                           | review workflow, reactions and text-only private questions приняты инкрементами; attachments/Telegram/E2E/visual открыты |
|    7 | `70df3da`…`c625d7b`  | [Phase 7A catalog](../../../pwa_tests/reports/phase7-classroom-catalog.md), [Phase 7B layout](../../../pwa_tests/reports/phase7-classroom-layout.md) | catalog + inherited layout + reload-safe Staff confirm приняты; assignment/delivery/oral открыты                         |
|    8 | —                    | —                                                                                                                                                    | —                                                                                                                        |
|    9 | —                    | —                                                                                                                                                    | —                                                                                                                        |
|   10 | —                    | —                                                                                                                                                    | —                                                                                                                        |
|   11 | —                    | —                                                                                                                                                    | —                                                                                                                        |

## Phase 7C checkpoint — 29 июля 2026

- Revisions `9aa3e20`…`70ad902` закрывают versioned assignment plan,
  deterministic distribution, compact reload-safe Staff editor, confirmed group
  change, history и stale/reassigning semantics.
- Revision `e0246e1` добавляет reviewed-hash Excel dry-run/apply и idempotent
  receipt. Proof: [assignment plan](../../../pwa_tests/reports/phase7-classroom-assignments.md)
  и [Excel import](../../../pwa_tests/reports/phase7-classroom-import.md).
- Актуальный gate: frontend unit **439 PASS**, Python PWA **1324 PASS / 3
  intentional skips**, lint/typecheck/production builds **PASS**. Delivery,
  oral, production rehearsal и owner visual approval остаются открыты.

## Phase 8 delivery observability checkpoint — 2 августа 2026

- Existing classroom delivery batches now expose owner-confirmed per-channel
  `selected`, `eligible`, `suppressed`, `queued`, `attempted`, `succeeded` and
  `failed` counters derived directly from immutable recipient rows.
- Staff shows `deliveredAny`, `deliveredAll`, `partial` and a privacy-safe
  disclosure of partial recipients. Failed-only Telegram retry keeps successful
  PWA delivery unchanged.
- No migration or mutable counter projection was introduced. Proof:
  [`phase8-classroom-delivery-observability.md`](../../../pwa_tests/reports/phase8-classroom-delivery-observability.md).
- Current gates: lint/typecheck **PASS**, frontend unit **565 PASS**, Python PWA
  **1498 PASS / 5 intentional skips**, Storybook browser **226 PASS** and
  production-build classroom E2E **9/9 PASS** in Chromium, WebKit and Firefox.
- Owner visual acceptance remains open; snapshots were not updated. Live-device
  Web Push and Telegram UI scheduled-queue reconciliation remain separate gates.

## Phase 10 Family-account UI checkpoint — 2 августа 2026

- Revision `e219337` добавил простые admin-only create/link/unlink API поверх
  `auth_accounts` и `family_student_links`; исходный пароль не возвращается и не
  попадает в audit.
- Текущий frontend-инкремент добавляет strict Zod-контракты, Staff client,
  компактную форму и несекретный reload-safe draft. Пароль отсутствует в draft
  schema и живёт только до успешной отправки.
- Storybook evidence: `Pages/Staff--family-account-management`; desktop 1280 px
  и mobile 390 px осмотрены вручную в light theme, snapshots не обновлялись.
- Proof:
  [`backend/API`](../../../pwa_tests/reports/phase10-family-account-backend.md) и
  [`frontend/Storybook/E2E`](../../../pwa_tests/reports/phase10-family-account-ui.md).
- Актуальные gates: lint/typecheck **PASS**, frontend unit **570 PASS**, Python
  PWA **1504 PASS / 5 intentional skips**, Storybook browser **227 PASS**,
  production-build authentication E2E **79 PASS / 8 intentional skips**.
- Phase 10 остаётся открытой: target Student/Family account batches, enrollment
  batch, metadata grid и Google parity/cutover ещё не завершены. Credential
  delivery решена: v1 хранит plaintext provisioning values и передаёт их
  внешнему email-script, а не Staff mail sender.

## Phase 10 checkpoint: индивидуальный Student web-вход — 2 августа 2026

- Admin может создать Student web-вход для существующего школьника без повторной
  передачи Telegram-токена через браузер; используется текущий token общего с
  ботом legacy-пользователя.
- На этом историческом checkpoint Directory предлагал
  `transliterated-surname-DD`; принятое позднее target-решение заменяет его
  explicit batch login и preview случайного `-NN` suffix при конфликте.
- Storybook evidence: `Pages/Staff--student-account-creation`.
- Проверки: 13 domain, 9 API integration, 573 frontend unit, 1508 Python PWA,
  22 Staff stories и production auth E2E **80 PASS / 10 intentional skips**;
  lint/typecheck и production build зелёные.
- Proof: [`pwa_tests/reports/phase10-student-account-creation.md`](../../../pwa_tests/reports/phase10-student-account-creation.md).
- Не закрыт batch provisioning/import; индивидуальный production E2E с отдельным
  синтетическим unprovisioned Student seed пройден.

## Phase 10 checkpoint: ежедневное пакетное создание Student web-входов — 2 августа 2026

- Admin выбирает небольшую пачку школьников с однозначными каноническими
  логинами; выбор хранится локально, переживает reload и не содержит секретов.
- Каждая строка проходит через существующий одиночный audited API. Успешные
  строки снимаются с выбора, частичные ошибки остаются для повторной проверки.
- Storybook: `Pages/Staff--student-account-batch-creation`; Staff browser gate —
  **23/23 PASS**. Production auth E2E — **81 PASS / 12 intentional skips**,
  включая создание двух настоящих аккаунтов после reload.
- Proof:
  [`phase10-student-account-creation.md`](../../../pwa_tests/reports/phase10-student-account-creation.md).
  Первоначальный bulk import/dry-run по исторической базе остаётся отдельным
  незакрытым gate.

## Phase 10 checkpoint: аудит синонимов задач — 2 августа 2026

- Merge/split записывают `problem_synonym.merged/split` в той же SQLite-транзакции,
  что и версионированная история состава; исходные задачи, посылки и результаты
  не переносятся.
- Synthetic audit failure полностью откатывает новое объединение. Searchable Staff
  audit получил фильтр «Синонимы задач» и русские подписи полей.
- Проверки: Python PWA **1524 PASS / 5 intentional skips**, frontend unit
  **578 PASS**, focused Storybook interaction/a11y **2/2 PASS**,
  lint/typecheck/production build **PASS**.
- Расписания пока остаются открытым audit-долгом: их транзакция находится внутри
  старого `PwaContentRepository`; неатомарная вторая запись сознательно не добавлена.
- Proof: [`phase10-staff-audit.md`](../../../pwa_tests/reports/phase10-staff-audit.md)
  и [`phase10-problem-synonym-api.md`](../../../pwa_tests/reports/phase10-problem-synonym-api.md).

## Phase 10 checkpoint: аудит доступов преподавателей — 2 августа 2026

- Полная замена областей teacher и `staff_scope.replaced` выполняются одной
  SQLite-транзакцией; append-only `staff_scopes` остаётся детальной историей.
- Audit показывает только публичные course/group IDs и counts. Synthetic failure
  полностью откатывает grant/revoke.
- Проверки: focused aiohttp **8/8 PASS**, Python PWA **1525 PASS / 5 intentional
  skips**, frontend unit **578 PASS**, focused Storybook **2/2 PASS**,
  lint/typecheck/production build **PASS**.
- Proof: [`phase10-staff-access-backend.md`](../../../pwa_tests/reports/phase10-staff-access-backend.md)
  и [`phase10-staff-audit.md`](../../../pwa_tests/reports/phase10-staff-audit.md).

## Checkpoint 2 августа 2026 — первый Staff statistics slice

- Реализован `/staff/statistics` поверх последнего завершённого immutable
  `analytics_runs`: course/group search state, teacher scope filtering,
  личные course metrics без group distribution, rank, percentile или student
  marker.
- Proof:
  [`phase10-staff-statistics.md`](../../../pwa_tests/reports/phase10-staff-statistics.md).
- Проверки: Python PWA `1533 passed / 5 skipped`, frontend unit `583 passed`,
  Storybook `233 passed`, lint/typecheck/build pass, production authentication
  E2E `87 passed / 12 intentional skips`; новый сценарий зелёный в трёх
  браузерах. Desktop и mobile-light просмотрены вручную, snapshots не менялись.
- Phase 10 остаётся незавершённой: нужны live operational counters, workload,
  oral/reach, scheduler и прочие перечисленные Google-cutover/admin gates.

## Checkpoint 2 августа 2026 — рабочая Staff-сводка

- `/staff/` переведён с prototype counters на scoped `GET /staff/api/v1/dashboard`.
- Dashboard агрегирует существующие review/support projections, независимые
  публикации, устные окна и admin-only ошибки classroom delivery, не отдавая
  student rows или тексты частных диалогов.
- Proof:
  [`phase10-staff-dashboard.md`](../../../pwa_tests/reports/phase10-staff-dashboard.md).
- Проверки: Python PWA `1542 passed / 5 intentional skips` в 8 workers,
  frontend unit `110 files / 586 passed`, Storybook `50 files / 236 passed`,
  lint/typecheck/build pass, production authentication
  E2E `90 passed / 12 intentional skips`; новый сценарий зелёный в Chromium,
  WebKit и Firefox. Desktop/mobile-light просмотрены, snapshots не менялись.
- Phase 10 остаётся незавершённой: target Student/Family и enrollment batches
  ещё не реализованы; active-group rule при нескольких allowed groups остаётся
  вопросом 3. Task-settings Google cutover зависит от владельческого принятия
  после реальной недели. Сам problem-workbook software path, его
  production-copy parity и classroom delivery/reach уже подтверждены; полный
  teacher workload остаётся отдельным продуктовым срезом.

## Phase 10 checkpoint: reconciliation импорта задач — 2 августа 2026

- Существующий XLSX workflow листов «Задачи»/«Старые» сверён от HTTP до
  production-build Playwright и не требует повторной реализации.
- Preview/apply/idempotent receipt/guarded rollback, synonym candidates и
  metadata grid образуют полный software replacement; parity настоящего файла
  против изолированной копии `db/vmsh.db`: `1813 unchanged`, ноль diagnostics.
- Сводный proof:
  [`phase10-problem-workbook-replacement.md`](../../../pwa_tests/reports/phase10-problem-workbook-replacement.md).
- Открыты только owner-run реальной недели и дата операционного cutover; import
  новых школьников является другим target workflow с уже принятым форматом.

## Общий Python gate на 8 workers — 2 августа 2026

- `make python-test` последовательно запускает legacy и PWA suites, каждый в
  восьми xdist workers; один смешанный collection запрещён разными runtime
  profiles.
- Legacy SQLite использует worker-specific filename/tmp_path, PWA — отдельную
  мигрированную временную SQLite на каждый worker.
- Финальный результат: legacy `121 pass / 1 skip` за 12,87 с; PWA `1542 pass /
5 skip` за 69,55 с; весь gate 85,53 с wall time.
- Test-only subprocess startup allowance устранён найденный под нагрузкой flake,
  а отдельная 50 ms timeout-проверка и production timeouts не менялись.
- Proof:
  [`python-xdist-gate-2026-08-02.md`](../../../pwa_tests/reports/python-xdist-gate-2026-08-02.md).

## Phase 11 checkpoint: fail-closed целостность frontend release — 2 августа 2026

- `verify`, `activate` и `rollback` теперь пересчитывают число файлов, размер и
  SHA-256 каждого Student/Family/Staff bundle до изменения `current`.
- Повреждённый manifest, изменённый или удалённый файл, посторонний root entry и
  любой symlink в release останавливают переключение; прежний release остаётся
  активным.
- Фактический release `945d21e` (456 файлов) совпал со своим манифестом. Focused
  release/toolchain regression — **14 PASS**; полный PWA Python gate — **1546
  PASS / 5 intentional skips** в восьми workers.
- Proof:
  [`phase11-static-release.md`](../../../pwa_tests/reports/phase11-static-release.md).
- Полный server rollback остаётся открытым до утверждения FQDN/layout и проверки
  backend revision, migrations, systemd и установленного nginx.

## Phase 11 checkpoint: dependency audit — 2 августа 2026

- `make dependency-audit` fail-closed проверяет все Python runtime/dev и все
  frontend production/dev зависимости из frozen lock-файлов.
- Python graph: **0 known vulnerabilities**; единственный adverse status —
  архивный `rsa` в legacy Google graph без известной уязвимости. Frontend graph:
  **0 known vulnerabilities** после минимальных patched overrides для
  `GHSA-mh99-v99m-4gvg`; ignored advisories отсутствуют.
- После совместимого обновления `aiohttp`/`aiogram`/`pydantic`: общий Python gate
  **121 + 1547 PASS**, historical Telegram **44 PASS**, frontend unit **586
  PASS**, Storybook **236 PASS**, lint/typecheck/build PASS.
- Proof:
  [`phase11-dependency-audit-2026-08-02.md`](../../../pwa_tests/reports/phase11-dependency-audit-2026-08-02.md).

## Phase 11 checkpoint: строгая production browser matrix — 2 августа 2026

- `make pwa-e2e-functional` собирает все три production bundles и проверяет их
  через один loopback origin, настоящий aiohttp и заново seeded E2E SQLite без
  MSW, Telegram, Google и production credentials.
- Три browser projects идут одновременно, но по одному worker на Chromium,
  WebKit и Firefox. Dedicated mutable personas устранили пересечения news,
  Family, classroom и Staff-auth scenarios; retries считаются ошибкой gate.
- Итог: **216 PASS / 12 intentional skips / 0 flaky / 0 retries** за 3,5 минуты.
  Production runtime и snapshots не менялись.
- Proof:
  [`phase11-production-e2e.md`](../../../pwa_tests/reports/phase11-production-e2e.md).
- Functional browser matrix закрыта. Отдельный `@visual` owner gate остаётся
  открытым; snapshots не обновлялись.

## Phase 5 checkpoint: настоящий media corpus — 2 августа 2026

- Server fallback обработал временные реальные JPEG с EXIF orientation/GPS и
  HEIC: итоговые WebP имеют длинную сторону не более 1920 px и не содержат GPS
  или `UserComment`.
- Повреждённый файл отклонён converter-ом, payload `25 MiB + 1 byte` — до
  запуска внешнего процесса. Исходные файлы не сохраняются в репозитории.
- Focused corpus: **5 PASS**, включая пять закреплённых по SHA-256 публичных
  фотографий математических материалов; полный PWA Python gate — **1552 PASS /
  5 intentional skips** в восьми workers. Proof:
  [`phase5-written-media-corpus.md`](../../../pwa_tests/reports/phase5-written-media-corpus.md).
- Media corpus gate Phase 5 закрыт; production service-profile и Hetzner S3
  остаются внешними Phase-11 gates.

## Phase 5 checkpoint: Storybook 1/2/10 страниц — 2 августа 2026

- Добавлены deterministic stories `product-submission--one-page`,
  `product-submission--two-pages` и `product-submission--ten-pages`; interaction
  проверяет перестановку двух страниц и точную верхнюю границу десять страниц.
- Storybook interaction/a11y gate — **50 files / 239 PASS**, strict TypeScript —
  PASS. Agent Storybook просмотрен на mobile-light 390 px и desktop 1280 px:
  горизонтального overflow нет, все десять страниц и подписанные controls
  доступны.
- Proof:
  [`phase5-written-consolidated-gates.md`](../../../pwa_tests/reports/phase5-written-consolidated-gates.md).
- Owner visual approval остаётся открытым; snapshots не обновлялись.

## Phase 0/11 checkpoint: SQLite photo workload — 3 августа 2026

- Два отдельных процесса записали в одну WAL-базу 16 письменных сдач, 32
  фотографии и 16 MiB representative file IO: 0.692s total, 0.033s p95, ни
  одного исчерпанного `SQLITE_BUSY`.
- Полный opt-in target вместе с 40-login burst: **2 PASS за 5.53s**. Допустимый
  user-visible busy budget для масштаба smoke равен нулю; широкие latency
  пределы являются только защитой от зависания, а не production SLA.
- Общий PWA Python gate после изменения: **1552 PASS / 6 intentional skips за
  72.83s** в восьми workers.
- Реальная конверсия HEIC/JPEG/WebP и browser outbox доказаны отдельными
  Phase-5 gates; этот тест намеренно изолирует SQLite metadata и file IO.
- Proof:
  [`phase11-two-worker-runtime.md`](../../../pwa_tests/reports/phase11-two-worker-runtime.md).
- Production concurrent-session telemetry и фактическая глубина offline outbox
  всё ещё неизвестны; они не выдаются за закрытые этим локальным измерением.

## Phase 6 consolidated checkpoint — 3 августа 2026

- Основной чек-лист сверен с 24 инкрементальными proof-файлами: queue/lease,
  atomic completion, concurrency/fault rollback, workspace draft, annotation,
  Student/Family projections, обе reaction-модели, admin inbox, append-only
  recheck, audience fan-out, support и Telegram PNG derivative реализованы.
- Production `make pwa-e2e-review`: **3/3 PASS** — один полный multi-context
  flow в Chromium, WebKit и Firefox против real aiohttp/seeded SQLite.
- Актуальные автоматические gates: `make python-test` — legacy **121 PASS / 1
  skip**, PWA **1552 PASS / 6 skip** в восьми workers; Storybook browser/a11y —
  **50 файлов / 239 PASS**; historical Telegram — **44 PASS**.
- Read-only rehearsal доказал, что legacy reactions нельзя точно связать с
  review round: безопасно переносимых строк **0**. Backfill/dual-write не
  добавляются, legacy-история остаётся у Telegram adapter.
- Сводный proof:
  [`phase6-consolidated-gates-2026-08-03.md`](../../../pwa_tests/reports/phase6-consolidated-gates-2026-08-03.md),
  runbook: [`review-workflow.md`](../../docs/review-workflow.md).
- Functional gate принят. Открыты owner visual acceptance без обновления
  snapshots, вложения в support, Telegram continuation и delivery wiring для
  уже готовой PNG-производной.

## Phase 7 consolidated checkpoint — 3 августа 2026

- Каталог, multi-course layout, deterministic assignment/history, one-time
  import, явная PWA/личная Telegram-рассылка, partial/retry report, публичное
  Student/Family состояние, устные окна и существующий result ledger свёрены с
  12 инкрементальными proof-файлами.
- Актуальный focused Python gate: **40 PASS** в восьми workers; contracts/clients
  Vitest: **8 файлов / 37 PASS**; общий PWA Python gate: **1552 PASS / 6 skips**.
- Последний успешный production matrix: classroom **9 PASS**, oral **3 PASS** в
  Chromium/WebKit/Firefox. Повтор 3 августа упал в macOS launcher на 0ms до
  assertions и не записан как новый PASS.
- Synthetic scale — 1500 очных школьников / 15 комнат, 0.55s; v1 намеренно не
  вводит print/export и оставляет `a11`–`a14`/workbook источником физической
  печати до отдельной второй версии.
- Proof:
  [`phase7-consolidated-gates-2026-08-03.md`](../../../pwa_tests/reports/phase7-consolidated-gates-2026-08-03.md),
  runbook:
  [`classroom-and-oral-workflow.md`](../../docs/classroom-and-oral-workflow.md).
- Software gate functionally ready. Открыты owner visual approval, реальный
  owner-reviewed classroom import/operational print rehearsal и свежий
  three-engine rerun после устранения внешнего macOS browser-launch сбоя.

## Phase 8 checkpoint: Telegram UI scheduled queue — 3 августа 2026

- Добавлен offline validator ручного инвентаря сообщений, запланированных в
  Telegram-клиенте: каждая строка получает одно решение
  `retain_in_telegram | cancel_and_recreate_in_staff | cancel_as_obsolete`.
- Hash mismatch после просмотра, дубли active intent/item/Staff draft и
  некорректная ownership-семантика блокируют cutover; одинаковый контент в
  разных destination разрешён.
- Aggregate report не содержит payload, Telegram IDs, destination keys или
  content hashes. Синтетический gate: **8 PASS**, CLI fixture: **ready, 4 items,
  0 blockers**; полный PWA Python regression: **1560 PASS / 6 intentional
  skips** в восьми workers.
- Bot API не умеет читать ручную scheduled queue, а официальный MTProto-метод
  user-only; user-account session намеренно не добавлен. Реальный owner-run
  inventory остаётся deployment gate перед будущим Staff scheduler.
- Proof:
  [`phase8-telegram-scheduled-queue-reconciliation.md`](../../../pwa_tests/reports/phase8-telegram-scheduled-queue-reconciliation.md),
  runbook:
  [`telegram-scheduled-queue-cutover.md`](../../docs/telegram-scheduled-queue-cutover.md).
- Удаление уже опубликованных channel posts этим срезом не закрывается и
  остаётся отдельным explicit reconciliation gate.

## Phase 8 checkpoint: удаление Telegram-поста — 3 августа 2026

- Global admin может явно отметить зеркальный Telegram-пост удалённым и
  исправить ошибочную отметку; teacher получает `403`.
- `If-Match`, обязательная причина и одна SQLite-транзакция защищают переход,
  а audit не содержит Telegram IDs, content или credentials.
- Проверки: focused Python **6 PASS**, полный PWA Python **1564 PASS / 6
  intentional skips**, frontend unit **111 файлов / 588 PASS**,
  lint/typecheck/production build — PASS.
- Storybook browser gate не стартовал из-за внешнего macOS Chromium
  `MachPortRendezvous`; это явно не засчитано как PASS, snapshots не менялись.
- Proof:
  [`phase8-news-source-deletion-reconciliation.md`](../../../pwa_tests/reports/phase8-news-source-deletion-reconciliation.md),
  runbook:
  [`telegram-news-deletion-reconciliation.md`](../../docs/telegram-news-deletion-reconciliation.md).

## Phase 8 checkpoint: локальная публикация PWA — 3 августа 2026

- Global admin может создать course/group публикацию с московским временем;
  teacher получает `403`, Telegram не вызывается.
- До срока post отсутствует в Student/Family feed, detail и in-app events;
  scheduled notification хранится с `deliver_after` и course context.
- Staff draft переживает reload и очищается только после server receipt.
- Story IDs: `pages-staff-local-news-composer--scheduled` и
  `product-news-moderation--scheduled-local`; snapshots не обновлялись.
- Focused Python **19 PASS**, полный PWA Python **1573 PASS / 6 skips**,
  frontend unit **113 файлов / 592 PASS**, lint/typecheck/build — PASS.
- Storybook не стартовал из-за внешнего macOS `MachPortRendezvous` code 141;
  ноль выполненных stories не записывается как зелёный gate.
- Proof:
  [`phase8-local-scheduled-news.md`](../../../pwa_tests/reports/phase8-local-scheduled-news.md),
  runbook: [`local-scheduled-news.md`](../../docs/local-scheduled-news.md).
- Открыт edit/reschedule; due-time foreground invalidation закрывается
  следующим checkpoint. Полное закрытие Phase 8 здесь не заявляется.

## Phase 8 checkpoint: due-time local-news invalidation — 3 августа 2026

- Уже открытые Student/Family/Staff вкладки получают
  `local-news-published` не позже следующего пятисекундного scheduler poll.
- Successful in-memory scan windows непрерывны; broker failure повторяет то же
  окно. Hidden publication не создаёт hint.
- Durable lease намеренно не добавлен: два worker могут безопасно вызвать два
  authoritative refetch несколько раз в неделю.
- Focused scheduler/realtime regression: **52 PASS**, полный PWA Python gate:
  **1578 PASS / 6 intentional skips**, Ruff — PASS. Proof:
  [`phase8-local-news-due-invalidation.md`](../../../pwa_tests/reports/phase8-local-news-due-invalidation.md).
- Local-news edit/reschedule и общий Phase 8 browser/visual gate остаются
  открыты; snapshots не менялись.

## Phase 8 checkpoint: редактирование будущей local news — 3 августа 2026

- Global admin редактирует текст и время только до исходного срока; owner не
  меняется. Immutable revision, optimistic version, notification reschedule и
  privacy-safe audit фиксируются атомарно.
- Скрытие будущей новости отменяет её ещё не наступившие события, восстановление
  создаёт их снова. На момент этого исторического checkpoint опубликованная
  новость отвечала `409`; последующий checkpoint исправления закрывает разрыв
  text edit с `updatedAt` и без repeat notification.
- Staff edit draft переживает reload и ошибку, изолирован по runtime, account,
  post и version и очищается только после server receipt.
- Story IDs: `pages-staff-local-news-composer--editing-scheduled`,
  `product-news-moderation--scheduled-local`. Full gates: frontend unit **113
  файлов / 592 PASS**, PWA Python **1580 PASS / 6 intentional skips**,
  Storybook **51 файл / 245 PASS**, production E2E news **9/9 PASS** в Chromium,
  Firefox и WebKit; lint/typecheck/build — PASS.
- Proof:
  [`phase8-local-news-editing-2026-08-03.md`](../../../pwa_tests/reports/phase8-local-news-editing-2026-08-03.md).
  Snapshots не обновлялись; owner visual acceptance остаётся открытым.

## Phase 10 checkpoint: черновик metadata grid — 3 августа 2026

- Реальный Staff content workflow хранит незавершённые matching/metadata
  правки в runtime/account/group-lesson/revision-scoped `localStorage`; другой
  Staff-аккаунт в том же browser profile не видит чужой draft.
- Storybook доказывает reload, account isolation, сохранение при `409`, explicit
  discard и cleanup после server receipt. Focused gate: **1 файл / 14 PASS**;
  полный browser/a11y gate: **50 файлов / 241 PASS**.
- Production `make pwa-e2e-content`: **3/3 PASS** без retry в Chromium, WebKit и
  Firefox. Реальный reload выполняется до сохранения metadata; после receipt
  browser key отсутствует.
- Исправлена обнаруженная E2E гонка: Staff invalidation больше не превращает
  уже подтверждаемую публикацию в молчаливый no-op; сервер повторно проверяет
  revision/matching/metadata как авторитетный gate.
- Сводный proof:
  [`phase10-metadata-grid-drafts-2026-08-03.md`](../../../pwa_tests/reports/phase10-metadata-grid-drafts-2026-08-03.md).
- Metadata draft gate закрыт. Визуальные snapshots не менялись; owner visual
  review и остальные незавершённые пункты Phase 10 остаются открыты.

## Phase 10 checkpoint: полный Google loader inventory — 3 августа 2026

- С реальным legacy-кодом сверены все шесть листов: `Задачи`, `Школьники`,
  `Учителя`, `Группы`, `_BotUIMsgs`, `_BotSettings`; для каждого названы
  колонки, SQLite side effects, Staff replacement, parity gap, recovery и
  cutover boundary.
- Отдельно зафиксирован operational риск: `/update_all` пишет домены
  последовательно без общей транзакции и до первого частичного cutover требует
  guard, чтобы не вернуть уже переключённый домен к Google-данным.
- Focused structural regression: **2 PASS**. Он извлекает worksheet names из
  настоящего loader и требует точного соответствия inventory и `/update_*`
  команд.
- Документ:
  [`google-loader-inventory-and-cutover.md`](../../docs/google-loader-inventory-and-cutover.md),
  proof:
  [`phase10-google-loader-inventory-2026-08-03.md`](../../../pwa_tests/reports/phase10-google-loader-inventory-2026-08-03.md).
- Matrix gate закрыт. Production cutover, дата owner acceptance и удаление
  credentials не объявлены; незавершённые домены перечислены явно.

## Phase 2 checkpoint: повторный local converter gate — 3 августа 2026

- Agent preflight с явным owner-local `pdflatex` подтвердил четыре capability:
  MiKTeX pdfTeX, `pdf2svg`, libwebp `cwebp` и ImageMagick.
- Synthetic smoke повторно прошёл обе цепочки: TikZ→PDF→SVG и
  raster→normalized PNG→WebP; HEIC decode advertised.
- Реальный converter corpus: **6 PASS**, включая JPEG/PNG/WebP/HEIC, фотографии
  математического канала, strip EXIF/GPS и rejection corrupt/oversized input.
- Proof: [`toolchain-local.md`](../../../pwa_tests/reports/toolchain-local.md).
- Local Phase 2 gate закрыт. Production service-account/staging probe остаётся
  отдельным незакрытым критерием Phase 11.

## Phase 9 checkpoint: course achievements в Family PWA — 3 августа 2026

- Family production page теперь показывает уже рассчитанные личные достижения
  внутри соответствующего курса ребёнка; Student и Family используют один
  UI-boundary словарь русских подписей.
- Неизвестный будущий rule code не показывается техническим текстом. Рейтинг,
  место, процентиль и сравнение с группой в блок не добавлены.
- Storybook ID: `Pages/Family--course-achievements`; focused browser/a11y —
  **12 PASS**, полный Storybook — **50 файлов / 242 PASS**.
- Полный frontend unit — **112 файлов / 590 PASS**, полный PWA Python в восьми
  workers — **1568 PASS / 6 intentional skips**; lint, typecheck и production
  build трёх приложений — PASS.
- Proof:
  [`phase9-family-achievements-ui-2026-08-03.md`](../../../pwa_tests/reports/phase9-family-achievements-ui-2026-08-03.md).
- Это functional checkpoint, не полное закрытие Phase 9: family-link import,
  completed-lesson/streak rules и owner visual acceptance
  остаются открыты. Snapshots не обновлялись.

## Phase 9 checkpoint: read-only Family-link import preview — 3 августа 2026

- Добавлен простой CSV preview для связей уже существующих Family accounts и
  Students: exact header, общая login normalization, duplicate guard и четыре
  состояния `create|restore|update|unchanged`.
- SQLite открывается только через `mode=ro` + `query_only`; integration test
  сверяет неизменность SHA-256 файла БД. Отчёт не содержит usernames или
  Student IDs — только counts, row numbers и stable codes.
- Focused parser/SQLite/CLI gate: **5 PASS**, Ruff format/check — PASS. Полный
  Python gate на восьми изолированных workers: legacy **121 PASS / 1
  intentional skip**, PWA **1573 PASS / 6 intentional skips**, **99,83 с** wall
  time. Proof:
  [`phase9-family-link-import-preview-2026-08-03.md`](../../../pwa_tests/reports/phase9-family-link-import-preview-2026-08-03.md).
- Production CSV dry-run и apply не объявлены готовыми. Этот compatibility
  preview не создаёт аккаунты и не принимает passwords; target Family batch
  отдельно принимает name/login/password/emails/child logins и хранит
  provisioning value для внешнего v1 mailer.

## Phase 11 checkpoint: media growth/orphan inventory — 3 августа 2026

- Read-only команда сравнивает migration-head SQLite с filesystem или точным
  configured S3 prefix; источники ключей ограничены `media_assets` и
  `news_media`.
- Missing/size mismatch, retained-deleted, unconfirmed и storage-only objects
  не смешиваются. Exact keys остаются в owner-local mode-0600 manifest, stdout
  содержит только aggregates.
- Delete отсутствует: этот срез даёт обязательный preview/diagnostic, но не
  меняет бессрочную admin-managed retention и не разрешает cleanup.
- Focused Python: **6 PASS**; полный PWA Python — **1586 PASS / 6 skip** в
  восьми workers; frontend unit — **594 PASS**; strict TypeScript и Ruff —
  **PASS**. Реальная agent Make-команда — **PASS**, нулевой изолированный
  inventory без diagnostics.
- Proof:
  [`phase11-media-inventory-2026-08-03.md`](../../../pwa_tests/reports/phase11-media-inventory-2026-08-03.md).
- Production Hetzner/service-account запуск, owner cleanup decision и audit
  остаются Phase 11 rollout gates.
- Временные ESLint-ошибки незавершённого Family route устранены в следующем
  Phase 8 checkpoint без ослабления правил.

## Phase 8 checkpoint: Family notification settings — 3 августа 2026

- Production `/family/profile/notifications` подключён к account-scoped
  preferences/push API вместо prototype. Переключатели есть только у пяти
  фактически доставляемых Family-категорий материалов и новостей.
- Student и Family используют один browser subscription handshake; loading,
  available, enabled, denied, unsupported и error имеют явные состояния.
- Full gates: frontend unit **114 файлов / 594 PASS**, PWA Python **1586 PASS /
  6 intentional skips**, Storybook **52 файла / 250 PASS**, production news E2E
  **12/12 PASS** в Chromium, Firefox и WebKit без retry; lint/typecheck/build —
  PASS.
- Proof:
  [`phase8-family-notification-settings-2026-08-03.md`](../../../pwa_tests/reports/phase8-family-notification-settings-2026-08-03.md).
  Weekly Family digest теперь имеет owner semantics: явная admin-отправка
  отдельно по группе, без auto-repeat после исправления; implementation и proof
  остаются открыты. Snapshots не обновлялись, owner visual acceptance открыт.

## Phase 8 checkpoint: явная Family lesson digest — 3 августа 2026

- Admin preview и отдельное подтверждение работают на конкретном
  `group_lesson`; состояние review queue не запускает отправку автоматически.
- Дедупликация выполняется по Family account + group lesson. Повторный POST не
  дублирует событие, но новый поздно связанный Family account получает итог.
- Family показывает account-scoped событие и шестую категорию «Итоги занятия»;
  Student не получает событие. Staff показывает ready, late-family,
  already-sent, no-recipient, loading и error states.
- Python integration **13 PASS**, contracts/client Vitest **12 PASS**,
  lint/typecheck и отдельные Staff/Family production builds — **PASS**.
  `make pwa-e2e-news` собрал все приложения/SW и поднял seed/aiohttp, но все
  browser cases остановились до test body на внешнем macOS launcher failure;
  E2E и visual acceptance не объявлены зелёными, snapshots не обновлялись.
- Proof:
  [`phase8-family-digest-2026-08-03.md`](../../../pwa_tests/reports/phase8-family-digest-2026-08-03.md).

## Phase 8 checkpoint: oral-window notifications — 3 августа 2026

- Открытие настроенного oral window создаёт account-scoped событие только для
  текущих online Student active group; Family и очные участники исключены.
- Startup catch-up, два worker, повторный scan и owner invalidation не создают
  дублей. Zoom URL/code не попадают в event payload.
- Focused Ruff и SQLite/aiohttp/scheduler gate: **11 PASS**; полный PWA Python
  в 8 worker’ах: **1588 PASS / 6 intentional skips**.
- Proof:
  [`phase8-oral-window-notifications-2026-08-03.md`](../../../pwa_tests/reports/phase8-oral-window-notifications-2026-08-03.md).
- `deadline` producer ждёт ответа на вопрос 2; physical push и owner visual
  acceptance остаются внешними gates.

## Phase 8 checkpoint: исправление опубликованной local news — 3 августа 2026

- Global admin исправляет только текст уже видимой local PWA news; owner и
  исходное время не меняются. Immutable revision, optimistic version и
  privacy-safe audit сохранены.
- Student/Family feed показывает новую revision и `editedAt`; Staff показывает
  «обновлено» и не даёт изменить время. Существующие notification event/delivery
  rows остаются неизменными, повторной рассылки нет.
- Story IDs: `pages-staff-local-news-composer--editing-published` и
  `product-news-moderation--published-local-correction`; production E2E-сценарий
  добавлен в `news-notifications.spec.ts`.
- Focused Python **12 PASS**, frontend unit **114 файлов / 594 PASS**,
  lint/typecheck/production build — PASS. Свежие Storybook/E2E browser gates не
  объявлены зелёными: Chromium launcher падает на macOS `MachPortRendezvous`, а
  E2E seed временно видит незавершённый parallel migration-0076 digest.
- Proof:
  [`phase8-published-local-news-correction-2026-08-03.md`](../../../pwa_tests/reports/phase8-published-local-news-correction-2026-08-03.md).
  Snapshots не обновлялись; owner visual acceptance открыт.

## Phase 11 checkpoint: public post-deploy HTTP smoke — 3 августа 2026

- Добавлена одна GET-only команда для уже переключённого public release. Она
  требует exact HTTPS FQDN и ожидаемый runtime instance, не читает credentials
  и не посылает login/другие write-запросы.
- Все три audience проверяются на health/runtime, production features,
  API-vs-SPA boundary и security headers. HTML shell обязан revalidate через
  `no-cache`; Student/Family manifest, icons и `no-store` service workers
  проверяются отдельно.
- Focused local aiohttp/unit gate: **16 PASS**; Ruff и structural nginx tests —
  **PASS**. Полный Python checkpoint записан в proof.
- Proof:
  [`phase11-production-http-smoke-2026-08-03.md`](../../../pwa_tests/reports/phase11-production-http-smoke-2026-08-03.md).
- Owner-approved FQDN, installed `nginx -t`, реальный запуск команды и
  authenticated/device checks остаются открытыми production gates.

## Phase 11 checkpoint: отдельный production systemd profile — 3 августа 2026

- Добавлены PWA-only unit/environment templates: два Gunicorn worker, Unix
  socket, `pwa-production`, prototype=false и базовое systemd hardening.
  Telegram/Google adapters остаются в отдельном legacy service.
- `make pwa-systemd-check` проверяет exact mode `0600`, обязательную env tuple,
  HTTPS origins, proxy socket, unresolved markers, worker boundary и отсутствие
  rolling reload/preload.
- Focused Ruff/pytest: **10 PASS**; полный PWA Python gate на восьми workers:
  **1616 PASS / 6 intentional skips**, 71,70 с.
- Proof:
  [`phase11-systemd-service-profile-2026-08-03.md`](../../../pwa_tests/reports/phase11-systemd-service-profile-2026-08-03.md).
- Реальные rendered paths/secrets, `systemd-analyze verify`, restart, socket
  ownership и public health/rollback остаются production gates.

## Phase 11 checkpoint: единый rollout checklist — 3 августа 2026

- Существующие rehearsal, release, systemd, nginx и public-smoke команды
  собраны в один операторский порядок с заранее записанным rollback target.
- Автоматические checks явно отделены от FQDN/service-user, production storage,
  real browser/device, alerts и owner acceptance. `NOT RUN` и browser launcher
  failure нельзя записывать как `PASS`.
- Evidence bundle запрещает credentials, cookies, PII и полные media URL;
  несовместимый schema rollback требует заранее выполненного rehearsal.
- Proof:
  [`phase11-production-rollout-checklist-2026-08-03.md`](../../../pwa_tests/reports/phase11-production-rollout-checklist-2026-08-03.md).

## Phase 10 checkpoint: backend course runtime settings — 3 августа 2026

- Migration `0077` и admin-only GET/PUT дают внутреннего typed owner четырём
  course-scoped значениям `_BotSettings`; default version `0` материализуется
  только после matching ETag.
- `reg_mode` остаётся глобальным legacy onboarding, game исключена из v1,
  `save_sol_mode` отсутствует, потому что новый pipeline всегда сохраняет
  content/submissions.
- Migration/schema/domain/API/audit gate: **29 PASS**; полный shared-worktree
  PWA Python gate — **1646 PASS / 6 skips** за **76,58 с** на восьми workers;
  Ruff и diff checks — PASS. Staff UI, Telegram compatibility read и production
  mapping/cutover остаются открыты.
- Proof:
  [`phase10-course-runtime-settings-backend-2026-08-03.md`](../../../pwa_tests/reports/phase10-course-runtime-settings-backend-2026-08-03.md).

## Phase 1 checkpoint: первый global admin — 10 августа 2026

- PWA auth startup после schema preflight создаёт login `admin` только если в
  `users` ещё нет global admin (`type = 128`). Password читается из
  `first_admin_password`, сразу хешируется Argon2id и не сохраняется/не
  журналируется в исходном виде.
- SQLite write повторно проверяет условие внутри одной транзакции: два gunicorn
  worker сходятся на одной записи. Повторный startup ничего не меняет; пустая
  база без настроенного password fail-closed не запускает auth.
- Удалён startup-вывод полного списка aiohttp endpoints. Остаются обычные
  короткие lifecycle-сообщения.
- Focused bootstrap/config/app-factory gate: **14 PASS**. Соседний
  auth/repository/HTTP/PWA regression gate: **134 PASS**. Ruff: **PASS**.
- Реализация и proof:
  [`apps/pwa_api/first_admin.py`](../../../apps/pwa_api/first_admin.py),
  [`db_methods/pwa/first_admin.py`](../../../db_methods/pwa/first_admin.py),
  [`test_first_admin_bootstrap.py`](../../../pwa_tests/integration/test_first_admin_bootstrap.py).

## Phase 10 checkpoint: создание сезонов в Staff — 10 августа 2026

- При отсутствии active season страница «Курсы и группы» показывает короткую
  форму создания сезона; в заполненном каталоге доступна кнопка «Добавить сезон».
- Admin-only `POST /staff/api/v1/seasons` создаёт сезон и audit-событие
  `season.created`; Storybook и snapshots по решению владельца не менялись.
- Проверки: Python API **5 PASS**, contracts/client **15 PASS**, Ruff,
  contracts/app-shell/staff typecheck и production Staff build — **PASS**.

## Deploy-first checkpoint: участники и первое занятие — 10 августа 2026

- Production-список `/staff/lessons` больше не показывает prototype-публикации:
  он читает реальный Staff dashboard и честно показывает пустое состояние.
- Admin может создать преподавателя с password-account, затем назначить ему
  course/group scopes существующим редактором. Legacy `users` без PWA
  `public_id` больше не попадают в новый каталог школьников; новые школьники и
  зачисления создаются существующим TSV preview/apply-процессом.
- Admin создаёт одно независимое `group_lesson` вместе с его собственным
  `lesson_window`; одинаковый номер другого уровня переиспользует только общий
  `course_lesson`. Черновик формы хранится в localStorage.
- Detail занятия показывает реальное расписание фаз, отдельно меняет
  opens/hint/solution и подтверждённый submission cutoff, а также позволяет
  явно закрыть приём сейчас. Дедлайн не связан с публикацией решения.
- Focused proof: course catalog/group lesson API **6 PASS**, staff access и
  enrollment API **13 PASS**, contracts/content/app-shell unit **32 PASS**;
  Ruff, ESLint, strict TypeScript и production Staff build — **PASS**.
- Storybook и аудитории не менялись.

## Deploy-first checkpoint: изоляция локального agent auth — 10 августа 2026

- Профили `pwa-agent` и другие prototype-профили больше не подхватывают
  production-подобные auth keys/peppers из общего test credentials-файла:
  без явных environment overrides используются детерминированные изолированные
  test-only значения профиля.
- Явно переданные environment overrides по-прежнему имеют приоритет; production
  поведение не менялось. Это позволяет запускать `make pwa-agent-api` независимо
  от legacy Telegram/Google и от содержимого локального credentials-файла.
- Focused auth config gate: **25 PASS**; Ruff: **PASS**.

## Deploy-first checkpoint: настоящее занятие 0 — 10 августа 2026

- Диагностическое занятие можно создать с номером `0`; это обычные
  `course_lesson`, `group_lesson` и `lesson_window`, поэтому загрузка LaTeX,
  сдача, проверка, фазы и публикации идут тем же production-путём, что и для
  последующих занятий.
- Migration `0078` меняет только нижнюю границу номера занятия и сохраняет
  существующие строки и идентификаторы. API, URL search params, Student,
  Family, Staff, progress и notification contracts принимают `0`.
- Реальный agent smoke: migration применена, `POST /staff/api/v1/group-lessons`
  вернул `201`, а Staff list/detail показали занятие `0`, независимый дедлайн,
  редактор фаз, загрузку трёх материалов и явную семейную итоговую рассылку.
- Focused API: **6 PASS**; contracts/client: **18 PASS**; schema inventory
  generate/check, Ruff и strict TypeScript — **PASS**. Storybook и код
  аудиторий не менялись.

## Phase 2 checkpoint: глобальный банк картинок — 13 августа 2026

- Migration `0079` добавляет неизменяемый регистр имён рисунков и
  версионированный кэш нормализованного TikZ; повторное имя всегда ведёт к уже
  зарегистрированному media asset.
- Source upload автоматически присоединяет найденные ресурсы. Для старых
  revision добавлены `POST .../assets/resolve` и кнопка Staff; TikZ cache hit не
  запускает `pdflatex` повторно.
- Архивный индексатор использует `rg --follow`, читает UTF-8/Windows-1251,
  учитывает команды из `newlistok.sty`, локальные picture-макросы и конечные
  анимации. Неупомянутые файлы не входят в импорт.
- Dry-run двух архивов: **2554 TeX**, **2391 выбранный файл**, **1352 unused**,
  **0 name conflicts**, **2 unresolved dynamic expressions**. Production apply
  остаётся после deploy migration и доступности production credentials/DB.
- Proof:
  [`phase2-content-picture-bank-2026-08-13.md`](../../../pwa_tests/reports/phase2-content-picture-bank-2026-08-13.md).

## Pilot content workflow corrections — 14 августа 2026

- Source upload автоматически собирает и кэширует TikZ; Staff больше не выбирает способ его подготовки. Внешний рисунок определяется по выбранному файлу, а уже известное имя переиспользуется до запроса новых bytes.
- Первая condition revision автоматически создаёт задачи; неизменная следующая структура сопоставляется позиционно. Ручное сопоставление осталось только для структурно изменённого условия. Общий `*-sol.tex` создаёт hint и solution revision и обязан совпасть с условием по порядку.
- Parser переносит тип из разделов «Тестовые / Письменные / Устные», а `\пункт` создаёт независимые problem rows `1а`, `1б`, … при едином визуальном условии.
- Staff preview переключает полноширинные PWA/Telegram renderers; Student full-sheet view получил те же controls сдачи после каждой задачи/пункта. Opaque ID и служебный канал ответа преподавателя из пользовательской копии удалены.
- Default rate limit уточнён: три неверных ответа за календарный час и пять любых попыток за календарный день.
- Proof: Python parser/repository/submission **199 PASS** и content HTTP
  integration **44 PASS**; Staff bulk/student task unit **13 PASS**; Staff content
  Storybook interaction **15 PASS**; ESLint, Stylelint, strict TypeScript,
  production build и `git diff --check` — **PASS**. Общий frontend suite
  сохраняет отдельные ранее существующие failures auth/session/realtime и не
  считается закрытым этим checkpoint.

## Pilot owner review: реальная загрузка и листок — 14 августа 2026

- Обычная новая condition revision больше не требует ручного сопоставления:
  точные задачи/пункты переиспользуются, а раскрытие старой задачи в несколько
  пунктов автоматически сохраняет первую ветку и создаёт остальные. Optimistic
  race двух вкладок перечитывает победившее состояние вместо тупикового `409`.
- Имя локального TeX-файла больше не является границей истории материала:
  ошибочно выбранный `*-n-sol.tex` можно заменить правильным `*-p-sol.tex` в
  том же hint/solution slot. Выбранные Dropbox-файлы сразу snapshot-ятся в
  память, чтобы повторная отправка не падала с `ERR_UPLOAD_FILE_CHANGED`.
- При открытии незавершённой revision Staff сам ищет рисунки в медиабанке,
  последовательно компилирует отсутствующие TikZ-фрагменты с актуальным ETag и
  продолжает сборку. Ручной выбор способа подготовки TikZ не требуется.
- Student использует читаемые ссылки `/tasks/<course>/<group>/<lesson>?task=…`;
  старый публичный UUID-route удалён. В простыне статус виден всегда, формы и
  переписка свёрнуты по умолчанию, а вопрос задаётся рядом с условием с полной
  предыдущей историей.
- Проекция статуса сравнивает время последней очереди и результата: завершённая
  перепроверка больше не остаётся в состоянии «Отправлено/На проверке» из-за
  старой строки очереди.
- Browser CSP разрешает `data:`-шрифт KaTeX и точный virtual-hosted origin
  production S3 bucket; Telegram `<b>/<i>` переводятся в безопасный browser
  dialect. Семантические пункты выводятся как `а)`, `б)` и получили компактные
  отступы.

## Phase 2 checkpoint: полный архивный parser gate — 13 августа 2026

- Рекурсивно найдено **2184** TeX-файла по точным lesson-маскам; **7** файлов
  с буквальным U+FFFD исключены, **2177** скомпилированы в правильных ролях
  condition/solution, найдено **25 827** problem nodes.
- Исправлено **47** однозначных дефектных TeX-файлов. Проверка через
  `/Users/sergeyshashkov/bin/pdflatex`: **44 PASS**, ещё **3** дошли только до
  ранее отсутствовавших image assets; синтаксических регрессий от исправлений нет.
- Parser получил bounded compatibility для общих legacy wrappers, math/list/
  table environments, локальных inert macro declarations, `npcopy`, layout
  groups/registers и TeX control spaces. `picture` остаётся warning; локальные
  DSL рисунков/домино и динамический `csname` не добавлены.
- Итог: **38** файлов с blocking errors, **3301** ошибок; из них **3295** —
  неизвестные локальные графические макросы, остальные — два non-lesson файла
  без задач, forbidden `csname` и одна таблица сверх wire-лимита 20 колонок.
- Focused parser/report gate: **80 PASS**. Полный список со строками и колонками:
  [`phase2-content-archive-all-errors.md`](../../../pwa_tests/reports/phase2-content-archive-all-errors.md).
  Краткий proof:
  [`phase2-content-archive-recursive-2026-08-13.md`](../../../pwa_tests/reports/phase2-content-archive-recursive-2026-08-13.md).

## Pilot follow-up: листок, дедлайн и production media — 14 августа 2026

- Ручное изменение дедлайна разрешено и для окна, материализованного из
  шаблона: отдельное подтверждение, optimistic version и audit сохранены.
- Solution web document теперь не повторяет условие и явно разделяет «Ответ» и
  «Решение». Межзадачные разделы остаются в полной простыне отдельным потоком:
  status/actions предыдущей задачи выводятся перед ними, а её решение их не
  захватывает.
- Student после дедлайна не видит редактор сдачи; переписка свёрнута, старый
  thread переиспользуется, `Cmd/Ctrl+Enter` отправляет сообщение или письменное
  решение. Hint/solution вынесены из блока ответа.
- Zoom viewer переведён с обрезаемого `transform` на реальный scroll-backed
  canvas. Локально просмотрен desktop light story
  `product-mathematical-document--zoom-canvas`; snapshots не обновлялись.
- Архив доступной неактивной группы принудительно перепроверяется при открытии.
  Production API отдельно подтвердил наличие опубликованного листка; stale
  client archive больше не должен скрывать его.
- Deploy использует и проверяет точный origin
  `https://d3ca76cf4cf5-images-bucket.s3.ru1.storage.beget.cloud`. Live nginx
  всё ещё требует обновления CSP и reload при следующем deploy.
- Focused Python **3 PASS**, frontend unit **10 PASS**, focused Storybook
  interaction **10 PASS**, ESLint, Stylelint, strict TypeScript, production
  build, shell syntax и `git diff --check` — **PASS**. Полная frontend suite
  сохраняет известные baseline failures auth/session/realtime.

## Pilot fix: границы задачи и межзадачного текста — 15 августа 2026

- Browser derivative разделяет statement задачи и следующий document-level
  текст. Разделы «Письменные/Устные задачи», пояснения и относящиеся к ним
  рисунки остаются в полной простыне между задачами, но status/actions
  предыдущей задачи появляются до них.
- В раскрытом Student solution больше нет второй копии условия и нет общего
  текста между задачами: остаются только непустые блоки «Ответ» и «Решение».
- Реальные `usl-00-n.tex` и `usl-00-n-sol.tex` проверены локальным compiler:
  у задачи 4 общий раздел находится только в `trailingBlocks`, а solution
  содержит четыре блока Answer/Solution. Focused Python **4 PASS**, contracts +
  content frontend **47 PASS**, lint, strict TypeScript, production build и
  `git diff --check` — **PASS**. Полная frontend suite сохраняет известные
  date-sensitive baseline failures auth/session/realtime.

## Pilot fix: повторная загрузка и публикация материала — 15 августа 2026

- Повторная загрузка тех же байтов стала идемпотентной: Staff получает уже
  существующую revision без `409` и без создания копии. После обновления
  compiler version эта же revision один раз возвращается в сборку, поэтому для
  применения исправленного parser больше не нужно добавлять пробел в TeX.
- Последняя готовая версия автоматически становится выбранной для проверки и
  публикации. Публичное состояние показывает номер версии и имя файла вместо
  внутреннего `content-revision-*`; подтверждение метаданных доступно и для
  корректной автоматически заполненной таблицы без фиктивного редактирования.
- Bulk upload после готовности всех файлов блокирует повторный запуск и пишет
  «Набор готов». Для отсутствующего внешнего рисунка сообщение ведёт к явной
  ссылке «Открыть недостающие рисунки» в строке соответствующей группы; TikZ
  по-прежнему собирается автоматически.
- Parser compiler v4 полностью поглощает двухаргументный
  `\\УстановитьГраницы{…}{…}`: `54mm`/`50mm` не попадают в PWA и Telegram.
  Telegram preview получил структурную типографику, а figure viewport —
  компактный canvas без пустой высоты вокруг изображения.
- Focused Python **3 PASS**, frontend unit **18 PASS**, focused Storybook
  interaction **18 PASS**, Ruff, ESLint, Stylelint, strict TypeScript,
  production build и `git diff --check` — **PASS**. Snapshots не обновлялись,
  visual acceptance владельцем остаётся открытым.

## Pilot follow-up: лента занятий и Staff-настройки — 17 августа 2026

- Student Tasks вместо селектора занятия показывает последние пять листков
  выбранной доступной группы целиком; следующие листки открываются порциями по
  пять. В каждой задаче и пункте рядом с номером видны статус и переход в
  читаемый task route, а компактные hint/solution находятся непосредственно
  после условия. Детальная страница объединяет ответы, письменные посылки и
  переписку в один блок «Ответы и обсуждение».
- Source-side `left*`/`right*` у рисунков сохраняется в web-document как
  `floatHint`. На широком экране renderer обтекает рисунок, только если тексту
  остаётся минимум `20em`, и ограничивает рисунок 70% ширины; на мобильном
  обтекание отключается.
- Staff получил явный logout, создание глобального admin и повышение teacher,
  а нефункциональный корень `/staff/problems` убран из навигации. Редактор
  семейных аккаунтов свёрнут в компактные строки.
- Course runtime settings теперь редактируют набор письменных вердиктов;
  review lease передаёт режим конкретного курса. Повторный claim своей же
  legacy-работы больше не определяется как чужой.
- Local news хранит исходный Telegram-compatible Markdown, показывает живой
  rich preview и публикует безопасную structured projection. Student больше
  не видит служебную отметку «Изменено в источнике».
- Добавлены domain/integration/unit проверки float metadata, Markdown,
  создания/повышения admin и повторного claim. Auth fixtures перенесены на
  устойчивый будущий срок: production expiry-check не менялся.
- Final gates: frontend unit **635 PASS**; PWA Python (8 workers)
  **1755 PASS, 6 SKIP**; lint, strict TypeScript, production build и
  `git diff --check` — **PASS**. Два legacy golden-corpus набора исключены из
  прогона из-за устаревших внешних manifests; golden-файлы и visual snapshots
  без приёмки владельца не обновлялись.

## Pilot follow-up: безопасное автоматическое PWA-обновление — 17 августа 2026

- Ожидающее обновление Student/Family автоматически активируется после
  завершённой навигации в другой раздел. Student также сообщает безопасный
  момент после подтверждённой сервером тестовой или письменной посылки.
- «Скрыть» убирает только уведомление и не отменяет обновление. Ручное действие
  называется «Обновить сейчас»; повторная попытка остаётся возможной после
  ошибки service worker.
- Frontend unit **636 PASS**, strict TypeScript и production PWA build —
  **PASS**.

## Pilot polish: читаемая простыня задач и размеры рисунков — 18 августа 2026

- Student Tasks убрал служебный заголовок, счётчик ленты и селектор курса при
  единственном курсе. На широком экране лист центрируется относительно всего
  viewport, а компактная шапка оставляет только переход на главную и тему.
- Номер, status и действие задачи/пункта перенесены в её смысловой заголовок.
  Межстрочный интервал уменьшен; перед новой задачей оставлен больший отступ,
  чем после заголовка.
- Web-document compiler v5 передаёт явную исходную ширину рисунка. Размеры в
  `mm`/`cm`/`pt` пересчитываются относительно 180-миллиметровой TeX-колонки,
  `\textwidth`/`\linewidth` сохраняются как доля, а рисунок без явного размера
  использует intrinsic dimensions и не растягивается. `left*`/`right*`
  сохраняют обтекание только там, где тексту остаётся не менее `20em`; на
  мобильном рисунок становится обычным блоком.
- Frontend unit **638 PASS**; focused width/float compiler checks **2 PASS**;
  PWA Python **1757 PASS, 6 SKIP**, кроме двух известных устаревших внешних
  golden manifests. Остальные gates приведены в отчёте текущего increment.
- При увеличении плавающий рисунок выходит из узкой колонки в полноширинный
  viewer с прокруткой; controls масштаба собраны в компактную строку и больше
  не растягивают листок.
- Family открывает текущий листок по читаемому маршруту
  `/family/tasks/{courseCode}/{groupCode}/{lessonNumber}`. Новые ссылки не
  содержат `groupLessonId` и `studentUserId`; при нескольких детях остаётся
  только короткий порядковый параметр `child`.
- Family использует для листка тот же центрированный paper-layout и
  математический renderer, что Student. Старый ID-route удалён: новый
  интерфейс больше не создаёт и не принимает такие адреса.
- Итоговые ESLint, Stylelint, strict TypeScript, production build и
  `git diff --check` — **PASS**; focused content **11 PASS**, width/float
  compiler **2 PASS**.

## Pilot polish: бумажная типографика и evidence вставок — 18 августа 2026

- `packages/content/src/content.css` и `packages/content/src/math-document.tsx`
  переводят Student-листок на локальный Computer Modern Serif (WOFF2 + OFL),
  колонку до `90ch`, русские переносы и адаптивное выравнивание: по ширине
  только при полной колонке, по левому краю на более узких экранах. Статус и
  действия находятся в строке номера задачи или пункта; рисунки получают
  почти белую подложку и в тёмной теме.
- `apps/student/src/student-task-detail-page.tsx`,
  `student-written-submission.tsx` и `student-support-pages.tsx` убирают
  повтор заголовка и дату публикации, сокращают редактор решения и называют
  диалог «Вопросы по задаче». Подсказка и решение открываются компактными
  действиями после вопроса без отдельной большой карточки.
- В `submission_entries` миграцией `0080` добавлены только агрегаты paste
  evidence: число вставок, суммарное число символов и время последней вставки.
  Clipboard content отдельно не хранится; draft/outbox/API сохраняют агрегаты
  вместе с исходной submission.
- Frontend unit **644 PASS**; focused contracts/content/product **25 PASS**;
  repository/API integration **94 PASS**; ESLint, Stylelint, strict TypeScript,
  production build и `git diff --check` — **PASS**. Полный PWA Python прогон:
  **1761 PASS, 6 SKIP**; после обновления generated schema artifacts отдельные
  schema/repository **48 PASS**, новый HTTP paste-contract **1 PASS**.
- Два оставшихся golden-manifest теста расходятся только в pretty-print
  `topLevelKeys`; семантический состав и hashes corpus не изменились, поэтому
  внешние golden manifests и visual snapshots без приёмки не обновлялись.

## Единый интерфейс листка школьника — 21 августа 2026

- «Открыть курс» на «Сейчас» (`apps/student/src/student-home-page.tsx`) ведёт
  на `/tasks` с фильтром курса и группы, а `/tasks/$courseCode/$groupCode/
$lessonNumber` без `?task=` рендерит ту же ленту (`StudentLessonFeedItem`),
  отфильтрованную на занятие. Отдельная простыня `CanonicalStudentWorksheet`
  удалена: интерфейс листка теперь один.
- В строке номера задачи статус прижат к началу, действие «Открыть» — к
  противоположному краю (`.vmsh-problem-actions-row` в
  `packages/content/src/content.css`). «Открыть» показывает задачу целиком
  через `CanonicalStudentTask`, который теперь использует тот же контейнер и
  ту же геометрию листа, что и лента (`STUDENT_SHEET_CONTAINER_CLASS`,
  `STUDENT_SHEET_CLASS`), поэтому бумага не съезжает вправо.
- `StudentProblemWorkspace` собирает один ряд действий под задачей: «Ответить»
  (открывает сдачу прямо в листке), «Задать вопрос»/«Вопросы по задаче»,
  «Подсказка», «Решение». Каждый раскрытый блок заканчивается повторным
  действием свернуть (`StudentCollapseAction`), потому что длинный материал
  уводит исходную кнопку за пределы экрана.
- Frontend unit, ESLint, Stylelint, strict TypeScript и production build —
  **PASS**. Golden-manifest и три storybook-теста расходятся так же, как на
  HEAD до изменения, и этой задачей не затрагиваются.

## Сдача задачи как переписка — 21 августа 2026

- `packages/product/src/task-chat.tsx` и `chat-composer.tsx` вводят общий
  диалог задачи: пузыри с явным автором (ученик, преподаватель, ИИ, бот,
  системное событие), вердикт внутри пузыря, статус доставки, разделители дат,
  и мессенджер-композер — строка ввода со скрепкой, кнопкой отправки и полосой
  миниатюр, где порядок страниц по-прежнему явный и доступен с клавиатуры.
  Состояния зафиксированы в `task-chat.stories.tsx` (8 stories, две с
  interaction-тестом).
- `apps/student/src/student-written-submission.tsx` показывает не «историю
  проверок» отдельным блоком, а всю переписку: свои отправленные сообщения с
  фотографиями (раньше ученик их вообще не видел), проверку с пометками на
  страницах и реакцией. Слияние entries и reviews вынесено в
  `student-written-chat.ts` и покрыто `student-written-chat.test.ts`.
  «Изменить отправленное решение» стало действием на своём последнем
  сообщении; алерты «отправлено» и «ждёт проверки» убраны — это видно по
  самому сообщению и его статусу доставки.
- `apps/student/src/student-test-answer.tsx` показывает тестовые попытки как
  разговор с автопроверкой: ответ ученика и ответ бота с бинарным вердиктом
  вместо списка «Последние ответы». Старые попытки подгружаются по кнопке над
  перепиской.
- Рендеринг stories вскрыл три дефекта, исправленных здесь же: `cn`
  (`twMerge`) считает токены размера шрифта цветами и молча выбрасывал
  `text-caption` рядом с `text-muted-foreground`; системное сообщение без даты
  повторно печатало разделитель дня; `entry.version` считает внутренние шаги
  загрузки, поэтому каждое отправленное решение помечалось «изменено».
  Общая проблема `cn` вынесена в отдельную задачу — она затрагивает и
  существующие компоненты, и визуальные снапшоты.
- Frontend unit **658 PASS**, ESLint, Stylelint, strict TypeScript и
  production build — **PASS**. Storybook: новые 8 stories проходят; три
  падающих теста те же, что на HEAD до изменения. На dev проверены живая
  письменная переписка с фотографиями и разговор с автопроверкой; тред с
  вердиктом преподавателя проверен только в Storybook — на dev сейчас нет
  проверенных решений.

## Сжатие диалога задачи — 21 августа 2026

- Пузырь стал плотнее: вердикт (`+`, `+/2`, `−`) идёт в строке текста без
  словесного дубля, время — в конце той же строки, доставка — только значком.
  Автоматическая проверка потеряла подпись автора: сторона пузыря и вердикт
  говорят всё сами. Подпись остаётся у живого человека и обязательна у ИИ.
- «Ответ в очереди — время создания уже зафиксировано, отправим при связи» и
  прочие формальные строки заменены на «Отправим, когда появится сеть» с
  кнопкой «Повторить»; счётчик фотографий и лимит попыток показываются только
  когда есть о чём сказать.
- `.vmsh-problem-workspace` очищает обтекание: плавающий рисунок условия
  больше не ужимает переписку под задачей.
- Масштаб рисунков и проверенных страниц опустился ниже натуральной ширины
  (лестница 0.25…4 и 0.25…3): большую картинку можно убрать с дороги.
  У пометок преподавателя высота ограничена 70vh, подпись сокращена и при
  увеличении прямо говорит, что область прокручивается.
- Frontend unit **658 PASS**, ESLint, Stylelint, strict TypeScript — **PASS**;
  storybook: те же три чужих падения, что и на HEAD.
