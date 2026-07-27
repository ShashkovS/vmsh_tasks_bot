# Принятые технические решения — 27 июля 2026

Этот документ фиксирует ответы владельца продукта на вопросы после первой версии Storybook и технические уточнения, возникшие при реализации. Он дополняет тематические документы в этой папке. При расхождении более позднее явное решение владельца имеет приоритет.

Второй блок ответов о типах задач, конфигурируемых вердиктах, очереди проверки, скрытых реакциях, подсказках и целевой AI-модели вынесен в [продуктовые UX-решения](product-ux-decisions-2026-07.md). Вместе эти два реестра покрывают весь questionnaire владельца; фазовые design-system файлы содержат производные acceptance requirements.

## Математика и content pipeline

- Единственный редактируемый источник условий, подсказок и решений — LaTeX.
- Новый конвертер строится на опыте `_external_pipelines/a16_html_from_tex.py`, `edt_tasks_parser.py`, `mathimg_endpoints.py` и `mathimg_service.py`, но становится тестируемым pipeline с нормализованным промежуточным представлением.
- Web-производная содержит безопасный HTML и исходные LaTeX-выражения. Формулы рендерятся KaTeX на клиенте; CSS и шрифты KaTeX входят в bundle и precache Student/Family PWA.
- У формул нет меню, copy helper, выделения и прочих необязательных интерактивных функций. Семантический MathML KaTeX для assistive technology сохраняется. Печать не снимается с web DOM и использует PDF pipeline.
- Telegram-производная предназначена для `sendRichMessage` Bot API 10.2+ и использует разрешённый Rich Message HTML, включая `<tg-math>` и `<tg-math-block>`. Это не legacy `sendMessage(parse_mode=HTML)`. Renderer хранит версию dialect и проверяет limits 10.2 (32 768 UTF-8 characters, 500 blocks, nesting 16, 50 media, 20 table columns); ограничения клиента/версии и fallback проверяются интеграционными тестами Telegram adapter.
- TikZ остаётся отдельным SVG-object в S3; HTML хранит ссылку и метаданные, а не inline SVG.
- Web compiler принимает asset только как единый строгий descriptor (public ID,
  SHA-256, безопасный URL, media type и dimensions), поэтому hash и URL не
  расходятся как независимые источники истины. Отсутствующий TikZ SVG остаётся
  blocking diagnostic.
- Планируется preview уже сгенерированного PDF. Он не является вторым print renderer и не допускает ручного редактирования производной.
- `pdflatex`, `pdf2svg`, `cwebp` и `magick` задаются optional полями общего backend config; defaults совпадают с именами команд и разрешаются через `PATH` service profile. Абсолютные paths допустимы как deployment override, `None` отключает capability. Missing required tool обнаруживается readiness/deploy preflight, а subprocess запускается argv-массивом без shell.

## Object storage и фотографии решений

- Production storage target — Hetzner S3-compatible через `aioboto3`; endpoint, region, bucket/access/secret задаются явно в production credential file. Выделенный opt-in test bucket пока находится в Beget и закреплён endpoint + SHA-256 bucket identity. Unit/agent/E2E остаются на filesystem/mock и не требуют secrets/network; legacy default Beget в `helpers.config` не является PWA production default.
- Браузер загружает файл через авторизованный aiohttp endpoint. Presigned browser upload не применяется: офлайн-очередь может ждать существенно дольше жизни подписи.
- Производные работы публично читаются по длинным непредсказуемым ключам. URL нельзя считать авторизацией; в operational logs он редактируется как пользовательский контент.
- Рекомендуемый key: `sol_imgs/user_{user_id}/{season_year}/{lesson_id}/{problem_id}_{created_at_utc}_{uuid}.webp`. Идентификаторы и UUID формирует/проверяет backend, а не браузер.
- До первого review lock школьник может изменить или удалить логическую отправку. После начала review исходная entry не меняется, но новый material можно дослать в тот же thread: его version меняется, и teacher обязан включить материал в текущий evidence перед complete. В транзакции результата attachment revision становится immutable; overwrite object key запрещён.
- Клиент декодирует изображение, уменьшает длинную сторону максимум до 1920 px и сохраняет только WebP. Оригинал не загружается и не хранится. Декодирование/re-encode обычно удаляет EXIF, отдельный EXIF pipeline не требуется.
- HEIC и другие неподдержанные браузером источники сначала пробуются на клиенте, затем отправляются через aiohttp в серверный image service на основе `mathimg_service.py` с ImageMagick/HEIC support. Результат всё равно WebP до 1920 px; исходник остаётся только во временном файле операции.
- Фотографии и история хранятся бессрочно до отдельной политики или ручной чистки bucket. Миграции из `VMSH_MEDIA_ROOT` нет: это новый storage namespace без существующих объектов.

## Authentication и security

- Логин школьника + текущий Telegram token как пароль — финальная совместимая модель, а не временная миграция и не Telegram OAuth.
- Student login генерируется как транслитерация фамилии + день рождения с обязательным разрешением коллизий. Family accounts содержат минимальное имя без email, создаются пакетно и имеют many-to-many links с детьми. Parent/teacher одного человека используют отдельные logins.
- Целевая сессия — две audience-scoped HttpOnly cookie: короткая подписанная `itsdangerous` access cookie и ротируемая refresh session в SQLite. Refresh token хранится в cookie только в raw-виде, в БД — HMAC/hash. Отзыв отдельного устройства удаляет DB session.
- Максимальный срок refresh session Student, Family и Staff — ближайшее 10 августа; access cookie существенно короче. У audiences разные имена и `Path`.
- `Secure`, `HttpOnly`, `SameSite=Lax` обязательны. Отдельный synchronizer CSRF token на первом этапе не вводится; unsafe endpoints дополнительно проверяют same-origin `Origin`/Fetch Metadata и принимают только ожидаемый content type.
- IP-level rate limiting выполняет nginx. Как минимум отдельная строгая zone нужна для login/auth; backend дополнительно ограничивает попытки по normalized login/account, чтобы распределённые IP не обходили защиту. Лимиты не заменяют authorization или idempotency.
- CSP вводится с первого production deployment. Политика должна явно разрешать собственные scripts/styles/fonts, audience WebSocket/API, фактически настроенный production media origin (целевой Hetzner), Web Push и Sentry ingest; inline/eval не добавляются без документированной причины.
- Аудит чтения чужих работ не нужен. Сохраняются все комментарии учителей, результаты проверки и изменения самой работы. Audit административных изменений, сессий и публикации остаётся.

## Realtime и offline

- Текущий production baseline — два gunicorn worker. NATS обязателен для live fan-out между ними; invalidation может быть общим или ограниченным audience. Любой reconnect всегда требует полного refetch из SQLite, cursor разных workers не сравнивается как durable offset. Owner scope требует authenticated WebSocket principal и остаётся частью auth-фазы.
- Принудительная очистка Web Storage/IndexedDB самим браузером после долгого отсутствия остаётся неизбежным платформенным риском; UI не обещает защиту от удаления данных браузером или устройства. При обычном reload, закрытии вкладки и PWA update drafts обязаны восстанавливаться. Student/Family не более двух раз мягко предлагают установку PWA, без блокирующих экранов.
- Целевой локальный бюджет — около 10–15 MB. Текст условий занимает малую часть; иллюстрации к недавно открытым материалам кешируются примерно на две недели и очищаются LRU/quota policy.
- Logout при непустом outbox показывает предупреждение. После явного подтверждения пользователя локальная очередь и drafts этого аккаунта могут быть удалены.
- Владелец подтвердил cold offline reading/drafts после прежнего online-входа
  без повторного credential и допустимость logout с непустым outbox после
  предупреждения. Безопасный implementation default делает cache account-scoped,
  называет состояние `offline-unverified`, ограничивает его локально известным
  `sessionExpiresAt` и после подтверждённого logout/account switch очищает cache,
  drafts и outbox, чтобы их не увидел следующий пользователь общего устройства.
- Незавершённая значимая работа Student/Staff переживает reload и update. Небольшие сериализуемые drafts и UI-state хранятся в `localStorage`, фотографии/blobs и durable outbox — в audience/account-scoped Dexie. Draft удаляется только после серверного receipt или явного discard; токены и cookies в эти хранилища не копируются.
- Повтор одного `idempotencyKey` с тем же payload hash возвращает исходный receipt. Другой payload получает conflict и требует нового ключа после явного действия пользователя.
- Операционные документы различают воскресный cutoff сдачи и более позднюю публикацию решений. Поэтому deadline хранится отдельным `submission_closes_at` в `Europe/Moscow`/UTC, а schedule и фактический timestamp solution publication не вычисляют его задним числом. Offline submission с client time до cutoff принимается и после поздней доставки; skew больше часа маркируется для диагностики. `SCHEDULE-01` закрыт: перенос публикации решения не двигает cutoff; дедлайн меняется только отдельным подтверждённым и аудитируемым действием.
- Publication form передаёт локальную минуту и IANA timezone группового занятия;
  server `zoneinfo` переводит её в UTC и отклоняет DST gap/fold. Timezone
  браузера и `Date.parse()` не определяют учебное расписание. Изменение cutoff
  и обычного расписания имеют разные optimistic operations и append-only audit.

## Домен

- Активных уровней сейчас три, но схема, контракты и UI допускают четвёртый и последующие уровни. Цвет назначается по `groups.sort_order`; неизвестные/лишние позиции получают доступный нейтральный fallback.
- Статистика сложности становится видна школьнику после окончания проверки занятия; автоматический grace period фиксирован и равен семи дням, а не является настройкой сезона.
- История группы/уровня/режима сохраняется. Текущий legacy source — `user_changes_log` (`change_type`, `new_value`, `ts`); миграция обязана сохранить и backfill эту историю.

## Frontend

- Sonner удаляется; notification primitives строятся на Base UI Toast.
- Sliding panels строятся на Base UI Drawer, а не на Dialog, замаскированном под Sheet.
- Графики: Visx поверх `d3-array`, `d3-scale`, `d3-shape`.
- Большие Staff grids: TanStack Table + TanStack Virtual.
- Новую DnD dependency не добавляем. В classroom planner аудитория выбирается компактным select; массовое перемещение использует выбор строк и один общий select. Порядок фотографий меняется кнопками вверх/вниз.
- Формам достаточно собственного малого слоя вокруг Base UI Field/Form semantics.
- Версии общих third-party dependencies задаются pnpm catalog.
- ESLint получает `eslint-plugin-jsx-a11y`; CSS проверяется Stylelint. React Compiler не используется.
- Базовый a11y gate действует и для Staff: обязательны labels, alt, корректный ARIA, контраст и axe. Для потенциальных специализированных Staff gestures не требуется отдельный полноценный keyboard-аналог, но текущий classroom flow целиком работает через обычные select/checkbox controls.
- Frontend Sentry включается только при наличии production DSN, без PII. Release/environment/audience передаются как tags; загрузка source maps настраивается серверными secrets позднее.
- Числового coverage gate нет. Тесты добавляются по риску и поведению, а не ради процента.

## Deploy и тесты

- GitHub Actions пока нет. Production обновляется серверным webhook: fetch exact revision, backup SQLite, frozen dependency sync, проверки/сборка изменившихся частей, migrations, controlled restart, healthcheck и detached post-deploy backup.
- Dependency detection учитывает root Python manifests и весь pnpm workspace, включая `vmshpwa/pnpm-lock.yaml`, `pnpm-workspace.yaml` и package manifests.
- Визуальные baselines пока считаются macOS-local artifacts; Docker normalization откладывается. Baseline меняется только после ручной проверки diff.
- Основной E2E и visual regression выполняются на production bundles через
  lock-aware test-only one-origin gateway с настоящим aiohttp. Три отдельных
  `vite preview` origin не моделируют production browser boundaries; общий
  runner не допускает конкурентной перезаписи dist/seed. Deploy дополнительно
  выполняет короткий smoke уже разложенных assets и service workers.
- PWA JSON error/request-ID middleware ограничивается `/student`, `/family`, `/staff` API/WS путями и не меняет ответы legacy dashboards.

## Дополнение по первому выпуску

- Первый production scope: сезон 2025–2026, занятия 39–41, все три уровня, полный online flow и admin-only планирование аудиторий. Интерфейс очного преподавателя для выставления результатов и печатный раздел остаются вне выпуска.
- Production hostname пока не выбран. Production и optional staging получают
  разные явно утверждённые lowercase FQDN; nginx template требует обязательный
  `@@PUBLIC_HOST@@` и не выводит hostname из legacy-сайта.
- Короткое maintenance window для migrations допустимо. SQLite backup три раза в день и перед deploy считается достаточным baseline.
- Полный S3 backup не требуется. Student images не versioned; отправленные teacher artifacts сохраняются immutable/versioned на уровне приложения или отдельной storage policy.
- Выпуск включается сразу для всех уровней. Критические сценарии вручную проверяются на доступных Android; iPhone — по возможности, автоматический WebKit остаётся обязательным.
- Для live integration используется test bot `@vmsh179devbot`, token которого хранится только в test config. Владелец предоставил canonical test-only Bot API `chat.id = -1003913815635` приватного `vmsh179devbot channel`; это pinned identity, а не правило преобразования произвольного UI ID. Bot добавлен admin; туда разрешено отправлять, редактировать и удалять synthetic/test content в пределах Telegram limits. До первого send отдельный read-only Bot API probe перепроверяет canonical identity/capabilities и фиксирует её в owner-only local SQLite; write-smoke берёт destination только оттуда. Unit/E2E используют RecordingBot и не зависят от live Telegram. Production channel задаётся отдельно для каждой группы в DB; серьёзные production alerts идут в служебную Telegram-группу.

## Аудитории и распределение очных школьников

- Модель разделяет глобальный каталог `classrooms`, наследуемые версии схемы «аудитория → группа» и отдельные версии плана школьников для занятия. У комнат нет capacity или weight.
- Нормализованное имя вычисляется как trim → Unicode NFKC → casefold и защищается уникальным индексом; исходное display-name сохраняет внутренние пробелы. Hard delete отсутствует, rename/archive/restore аудитируются.
- Первая правка унаследованной схемы материализует draft. Изменение схемы помечает связанный план `stale`; подтверждение требует нового preview/recalculation.
- Автораспределение детерминировано: прежняя допустимая комната, иначе наименее заполненная комната группы, затем естественная сортировка имени и стабильный ID как последний tie-breaker.
- Скрытие используемой комнаты переводит текущие назначения в `reassigning`; восстановление не возвращает их автоматически. Прошлые подтверждённые планы неизменны.
- Student и Family получают read contract `not_applicable | reassigning | assigned`; owner-scoped `classroom.assignment.changed` после confirm только инвалидирует их состояние. Персональная доставка создаётся отдельным admin-only batch после preview: PWA даёт Student in-app/push, Telegram отправляет Student личное сообщение через бота. Family classroom delivery не получает; изменение плана не вызывает автоматическую повторную рассылку.
- Test S3 bucket, `@vmsh179devbot` и приватный test channel разрешены для opt-in smoke: можно создавать/читать/удалять объекты под disposable `integration/<run-id>/`, проверять public GET и отправлять/edit/delete только synthetic Telegram content. Production credentials/channels для этих тестов запрещены.
- Начальное заполнение — одноразовый dry-run/import Excel-export с `IDd`, `Уровень`, `Аудитория`; это не постоянный Google/Excel adapter.
- Classroom planner показывает цвет группы, `очно/распределено`, компактные flex-wrap-комнаты, отдельную область неназначенных и всегда сортирует школьников по фамилии/имени. В строке доступны nullable возраст на сегодня, класс и автоматически вычисленная сила 0–10; у комнаты — count и средние возраст/класс/сила без неизвестных значений. Все три средних округляются до одного знака.
- Поиск по имени нормализует регистр, `ё/е`, пробелы и порядок слов, допускает небольшие опечатки, подсвечивает результат и позволяет перейти к нему. История подтверждённых аудиторий школьника доступна из его строки.
- Назначение в комнату другой группы возможно только вместе с явно подтверждённой сменой группы. Classroom draft накапливается локально и восстанавливается после reload до явного сохранения/подтверждения.

## UI-контракты, уточнённые 25 июля

- Все 23 текущих `ANS_TYPE` из `helpers/consts.py` имеют явное представление. Клиентская format validation зеркалит `strip()+fullmatch` из `helpers/checkers.py`, включая problem `ans_validation`; correctness решает server. Fixed tuple не показывает «Отправится», list preview строится после parsing, `SELECT_ONE` передаёт видимый label.
- Review detail — компактная queue и одна хронологическая колонка `evidence → существующий thread → новый teacher reply/verdict`. Teacher verdict/reaction controls маленькие, но exact wording всегда виден; internal reaction выбирается также через `⌘/Ctrl + Alt + 1…4`, включая момент, когда фокус остаётся в комментарии.
- В metadata grid есть отдельные task type и answer type. Обе ячейки могут быть dropdown, не ломая прямоугольную TSV copy/paste. Condition, hint и solution каждого уровня имеют отдельные publish/schedule/rollback операции.
- Telegram Rich Message поддерживает headings, paragraphs, emphasis/mark/sub/sup/spoiler, links, lists, quotes, code, details, tables, media и math. Новые условия публикуются текстом, а не screenshot; fixture corpus — `_external_pipelines/ChatExport_2026-07-25`.
- Выбранные submission photos сразу показывают thumbnail. Отдельная пользовательская квитанция/reference number не нужна; idempotency receipt остаётся техническим API-понятием.
- Полный broadcast workflow откладывается во вторую фазу и проектируется вместе с Markdown editor, previews, расписанием и delivery state. Story первой фазы не имитирует отправку.

## Значения, фиксируемые при реализации и развёртывании

- production Hetzner bucket/media hostname, Sentry ingest, API/WS и окончательной CSP;
- короткий access-cookie TTL;
- точная команда/systemd units production webhook;
- точный suffix/ручной workflow для коллизии сгенерированных student logins.

## Решение 26 июля: независимые курсы и группы

Принята иерархия `season → course → group → lesson`, per-course enrollment/attendance/progress/notifications, независимые group schedules/content/Telegram bindings, логические синонимы без переноса concrete data и `in_person_event` для групп разных курсов. Текущие группы backfill-ятся в «Математика 5–7» с сохранением legacy IDs. Authoritative спецификация: [courses-groups-and-lessons.md](courses-groups-and-lessons.md).
