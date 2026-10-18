# Общий выпуск MCP и производительности — 18 октября 2026

Владелец разрешил commit/push и deployment на vmsh.shashkovs.ru и prep.leaders.tech.
Текущий этап: интеграция и проверка общего source; production ещё не обновлён этим выпуском.

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

1. Общий source, manifest и gate; публикация exact tree в production-ветке.
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
