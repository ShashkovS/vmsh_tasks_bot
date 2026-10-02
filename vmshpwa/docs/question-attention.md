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
testing связывают это решение с реализацией. Production-выпуск не выполнялся.
Порядок выпуска: миграция → backend → frontend; конкретные шаги — в отчёте.

## Выпуск — 2 октября 2026 (в работе)

Commit/push и оба деплоя разрешены владельцем. VMSH использует существующий
webhook ветки `vmshpwa`; prep.leaders.tech —
[reviewed SSH cutover](../../docs/deploy/tlf-app/deploy_support_attention.sh).
[Read-only checker](../../docs/deploy/tlf-app/support_attention_data_check.py)
сравнивает каждую старую таблицу, сообщения и версии, проверяет владельца/автора/время
новых отметок и полноту baseline. Резервные копии сохраняются; NATS и credentials
не меняются. Backend должен пройти health до активации frontend. После повторного
открытия writers аварийный путь сохраняет новые receipts и Zoom-события, используя
совместимый старый frontend. Результаты production будут записаны после выпуска.
