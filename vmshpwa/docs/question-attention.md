# Вопросы: внимание и прочтение ответов

Принято владельцем 1 октября 2026. Оранжевая точка у «Вопросы по задаче» означает
последнее человеческое сообщение ученика; красная пульсирующая — хотя бы один
непросмотренный ответ преподавателя/администратора и имеет приоритет.

«Новые ответы (N)» над `/student/tasks` считает задачи по всем доступным курсам
и группам, скрывается при нуле и перебирает их от старейшего непрочитанного ответа.
Переход переключает контекст, подгружает листок, раскрывает вопросы и прокручивает
к ответу. URL `question=<threadId>` восстанавливает переход. Отдельных новых списков
и фильтров нет; существующая история сохраняется.

Каждый ответ отмечается после 3 непрерывных секунд видимости 75% от min(высота
ответа, высота viewport) в активной вкладке. Скрытие сбрасывает таймер. Только
серверное подтверждение гасит точку; ошибки повторяются при восстановлении связи
и видимости. Прочтение общее для устройств ученика; уведомление не прочитывает
ответ, ответ погашает соответствующие уведомления. Миграция считает старые ответы
прочитанными без изменения сообщений/версий. Reduced motion отключает анимацию.

Реализация: [миграция](../../migrations/0107.pwa_support_entry_reads.sql),
[домен](../../models/pwa/support_attention.py), [SQL](../../db_methods/pwa/support_attention.py),
[API](../../apps/pwa_api/support_routes.py), [контракты](../packages/contracts/src/support.ts),
[клиент](../packages/app-shell/src/support-client.ts),
[переписка](../apps/student/src/student-support-pages.tsx),
[лента](../apps/student/src/student-tasks-page.tsx).

## Контракты и совместимость

Student-клиент отправляет `X-Vmsh-Support-Attention: 1`; thread и summary получают
`attentionState`, `unreadReplyCount`, `firstUnreadEntryId`, а entries — nullable
`readAt`. Поля в Zod необязательны для старых payload/кэшей. Без capability-header
backend сохраняет прежнюю строгую проекцию, Staff-контракт также сохраняется.

`POST /student/api/v1/questions/{threadId}/read` принимает
`{schemaVersion: 1, entryIds: [...]}`: 1–100 уникальных public ID. Владелец, тред
и авторство проверяются для всего набора до атомарной записи. Повтор возвращает
первое серверное `readAt`. Ответ: `schemaVersion`, `readEntries[{entryId,readAt}]`,
`requestId`.

`GET /student/api/v1/questions/attention?afterThreadId=...` возвращает
`unreadTaskCount` и nullable `nextTarget` с `threadId`, `courseId`, `groupId`,
`groupLessonId`, `problemId`, `firstUnreadEntryId`. Порядок — старейший
непрочитанный Staff-ответ, затем его внутренний ID; переход закольцован. Если
предыдущая задача уже прочитана/недоступна, выбирается первая оставшаяся.
Счётчик включает только опубликованные и доступные сейчас задачи, включая
сохранённую публикацию с frozen figure layout.

Read подтверждает лишь перечисленные ответы; новый ответ во время запроса
остаётся непрочитанным. Query cache обновляется после подтверждения и
инвалидируется вместе с историями/счётчиком/уведомлениями. Realtime пересчитывает
те же Student-ресурсы на других устройствах. Уведомление, созданное после
просмотра ответа, наследует его отметку.

## Проверка и выпуск

Реализовано локально: [результаты и снимки](../../pwa_tests/reports/question-attention/README.md).
Шесть E2E прошли в Chromium/Firefox/WebKit; проверены RU/EN, light/dark, mobile и
reduced motion. Backend/контракты/видимость, миграция, схема, lint, TypeScript,
i18n и build проверены; ограничения общего backend gate описаны в отчёте.
Новые состояния — [stories](../packages/product/src/question-attention.stories.tsx),
временное правило — [тесты](../apps/student/src/visible-support-reply.test.tsx),
переход/устройства — [E2E](../e2e/support-dialogue.spec.ts),
права/публикации — [backend](../../pwa_tests/integration/test_support_attention.py).
Второй курс в отдельном `support`-прогоне создаёт
[защищённый seed](../scripts/seed_e2e_support_navigation.py); его
[тест](../../pwa_tests/test_e2e_support_navigation_seed.py) проверяет реальный
Student access. Состояния Waiting/Unread/Read прошли Chromium Storybook/a11y gate.

Оба STATUS.md и фазы Student reading / review / notifications и Product / flows /
testing связывают это решение с реализацией. Production-выпуск завершён 2 октября
2026: миграция → backend → frontend. Результаты — ниже и в отчёте.

## Production — 2 октября 2026

Commit/push и оба деплоя разрешены владельцем. VMSH использует существующий
webhook ветки `vmshpwa`; prep.leaders.tech —
[reviewed SSH cutover](../../docs/deploy/tlf-app/deploy_support_attention.sh).
[Read-only checker](../../docs/deploy/tlf-app/support_attention_data_check.py)
сравнивает каждую старую таблицу, сообщения и версии, проверяет владельца/автора/время
новых отметок и полноту baseline. Резервные копии сохраняются; NATS и credentials
не меняются. Backend должен пройти health до активации frontend. После повторного
открытия writers аварийный путь сохраняет новые receipts и Zoom-события, используя
совместимый старый frontend.

Релиз `5bb8d38227df59503cfcf45ec1c489726d9bb55d` отправлен в `origin/vmshpwa`
после rebase поверх шести новых metadata/i18n-коммитов. Повторные gates: 38 backend,
20 frontend, schema (500 объектов), TypeScript, lint и оба i18n — PASS.
Ручной checker отдельно прошёл up/down/up и обнаружение изменения старой таблицы.

| Портал                            | Способ               | Активный frontend                         | Миграции         | HTTP smoke |
| --------------------------------- | -------------------- | ----------------------------------------- | ---------------- | ---------- |
| [VMSH](https://vmsh.shashkovs.ru) | существующий webhook | `5bb8d38227df-20261002055653`             | 79, включая 0107 | 25 PASS    |
| [TLF](https://prep.leaders.tech)  | reviewed SSH cutover | `tlfprep-20261002-questions-5bb8d38227df` | 79, включая 0107 | 25 PASS    |

VMSH backups `vmsh-before-deploy-20261002055755.sqlite3` и
`vmsh-after-deploy-20261002055822.sqlite3` подтверждают одинаковые hash всех
877 support entries и 383 support threads, включая сообщения и версии. Baseline
содержит 422 Staff-ответа и ровно 422 валидных receipt; backlog отсутствует.
Runtime schema current, quick_check ok, NATS PID 1409 прежний; PWA, Telegram
и analytics timer активны, maintenance снят. Предупреждение autodeploy о
`docs/deploy` относится к новому TLF cutover; установленные webhook/nginx/systemd
артефакты VMSH не менялись и переустановка не требуется.

TLF record:
`/web/vmsh_tasks_bot/deploy/releases/tlfprep-20261002-questions-5bb8d38227df/`.
Up/down/up на копии и сравнение всех 154 старых product tables при остановленных
PWA/Zoom/analytics writers — PASS. В TLF ещё нет support entries/threads, receipts
пусты; схема актуальна и quick_check ok. Credentials checksum совпал, NATS PID
1936264 прежний. Backups `20261002T055732.874226Z` и `20261002T055913.981909Z`
имеют integrity ok и сохраняют три raw Zoom receipts. PWA, Zoom и analytics timer
активны; backend health проверен до активации frontend.

Все четыре приложения на каждом портале имеют production provenance, MSW/prototype
отключены, media origin прежний. Публичные Student bundles содержат attention API,
capability header и глобальный счётчик. Неавторизованные запросы attention/read
возвращают 401/403. [Машиночитаемое подтверждение](../../pwa_tests/reports/question-attention/production-proof.json).

Production-проверки были read-only: новые ответы, посылки и Zoom-события не
создавались. Полный сценарий ответа/перехода/прочтения на двух устройствах проверен
в изолированном E2E во всех трёх движках. Documentation follow-up может обновить
VMSH source HEAD; compiled release и backend сохраняют указанную feature-версию.
