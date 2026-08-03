# Phase 8 proof: редактирование будущей локальной новости

Дата проверки: 3 августа 2026 года.

## Проверяемый результат

- Global admin может изменить полный plain text и время ещё не наступившей
  course/group local publication через
  `PATCH /staff/api/v1/news/{postId}/local` с `If-Match`.
- Получатель не меняется. Каждое содержательное изменение создаёт immutable
  `news_revisions`; возврат к прежним тексту и времени также создаёт новую
  ревизию, не меняя старые записи.
- Заголовок post, visibility version, revision, privacy-safe audit и перенос
  `notification_events.deliver_after` входят в одну SQLite-транзакцию.
- Скрытие будущей публикации удаляет ещё не доставленные события; восстановление
  создаёт Student/Family events снова. Уже опубликованная запись отвечает
  `409 local_news_already_published`, пока не решён вопрос 7.
- Staff edit draft хранится по runtime/account/post/version и очищается только
  после подтверждённого ответа сервера.

## Реализация и трассировка

- SQL: `db_methods/pwa/local_news.py`.
- Правила revisions и schedule: `models/pwa/local_news.py`.
- HTTP и audit: `apps/pwa_api/news_moderation_routes.py`.
- Контракты и клиент: `vmshpwa/packages/contracts/src/news.ts` и
  `vmshpwa/packages/app-shell/src/news-moderation-client.ts`.
- Staff UI: `vmshpwa/apps/staff/src/staff-news-page.tsx` и
  `vmshpwa/apps/staff/src/staff-local-news-composer.tsx`.
- Storybook: `pages-staff-local-news-composer--editing-scheduled` и
  `product-news-moderation--scheduled-local`.

## Автоматические проверки

- Focused Python moderation/scheduler integration: **18 PASS**.
- Focused frontend unit: **3 файла / 6 PASS**.
- Полный frontend unit: **113 файлов / 592 PASS**.
- Полный PWA Python: **1580 PASS / 6 intentional skips**.
- ESLint, Stylelint, strict TypeScript и production build трёх приложений:
  **PASS**.

Browser gates на этой машине не получили продуктового результата. И
`make pwa-storybook-test`, и production-preview `make pwa-e2e-news` остановились
до выполнения первой story/page: Chromium воспроизводимо падает даже на
прямом `about:blank` smoke с
`bootstrap_check_in ... MachPortRendezvousServer ... error 141`; WebKit и
Firefox также завершаются при launch. Совместимые с Playwright 1.61.1 browser
binaries установлены, поэтому missing executable исключён. Это **BLOCKED**, а
не PASS; browser/a11y/E2E нужно повторить вне текущего macOS bootstrap sandbox.

Visual snapshots не обновлялись. Browser/visual принятие владельцем и правило
исправления уже опубликованной новости остаются открытыми.
