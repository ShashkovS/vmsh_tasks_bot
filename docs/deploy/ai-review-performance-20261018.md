# Общий выпуск MCP и производительности — 18 октября 2026

Владелец разрешил commit/push и deployment на vmsh.shashkovs.ru и prep.leaders.tech.
Текущий этап: общий release gate и репетиции миграций PASS; начинается штатный SSH push → webhook ВМШ и отдельный штатный выпуск TLF. Production ещё не обновлён этим выпуском.

## Состав и проверки

- [MCP-помощник и инструкции](../../vmshpwa/docs/ai-review-assistant.md):
  приватные предложения, независимое использование комментария/вердикта,
  массовые предыдущие комментарии/посылки и учебный контекст прошлых занятий.
- [Performance release 8b7ce809](../performance/followups-20261018.md):
  scoped reads/refetch, статистика, persistent analytics, фото, push и offline refresh.
- Общая схема: performance 0120/0121, затем
  [0122.ai_review_assistant.py](../../migrations/0122.ai_review_assistant.py), 532 objects.
  Ранее помощник имел номер 0120 только в невыпущенной ветке; рабочие DB его не применяли.
- Требуются общий release gate и свежая server-side SQLite rehearsal на обоих серверах.
  Полные production DB не скачиваются. Бизнес-таблицы, настройки и NATS сохраняются.

## Порядок выпуска

1. Общий source и gate; обычный commit → git push origin HEAD:vmshpwa по SSH.
   ВМШ обновляется штатным webhook; TLF сохраняет существующий ручной deployment.
   GitHub API для публикации исходников или изменения refs не используется.
2. TLF: verified backup, stage build, SQLite rehearsal и performance guard;
   maintenance, остановка writers, миграции, сверка старых бизнес-таблиц и пустых новых,
   запуск PWA/Zoom, static activation, HTTP/assets/auth smoke, backup.
3. ВМШ: штатный root-owned deploy с собственным lock/backup/rehearsal;
   smoke и контроль schema/services/maintenance.
4. Проверка token-only MCP boundary и нового Staff UI на обоих origin.
   Личный постоянный ключ создаёт пользователь; production-предложения ученикам не публикуются.
5. Окончательная квитанция, STATUS и инструкция Codex.

Прежние perf-проверки и нынешние локальные проверки не подменяют production proof.
При ошибке после migration трафик не возвращается на неподтверждённую схему.

## Проверка общего исходника

[Release gate](../../pwa_tests/reports/ai-review-assistant-20261018/combined-release-gate.json):
3083 Python / 12 SKIP, 1136 frontend, 384 Storybook, 159 E2E / 18 SKIP,
Chromium/Firefox/WebKit; format/types/lint/i18n/build PASS, source unchanged.
Server-local up/down/up, 168 business table hashes, performance guard и integrity:
[ВМШ](../../pwa_tests/reports/ai-review-assistant-20261018/vmsh-rehearsal.json),
[TLF](../../pwa_tests/reports/ai-review-assistant-20261018/tlf-rehearsal.json).
