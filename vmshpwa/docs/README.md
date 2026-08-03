# Документация `vmshpwa`

`vmshpwa` — новый интерфейс существующей системы ВМШ 179. Он не является отдельным продуктом или новым backend: Student PWA, Family PWA, Staff SPA, Telegram-бот и legacy-интерфейсы используют одну доменную модель и одну SQLite-базу в рамках каждого runtime.

## Карта документов

- [Продукт и роли](product-and-roles.md)
- [Недельный цикл](weekly-lifecycle.md)
- [Архитектура](architecture.md)
- [Изоляция runtime и команды](runtime-isolation.md)
- [Аутентификация и безопасность](authentication-and-security.md)
- [Realtime, offline и уведомления](realtime-offline-and-notifications.md)
- [LaTeX/content pipeline](latex-content-pipeline.md)
- [Зеркалирование Telegram-новостей](telegram-news-mirroring.md)
- [Стратегия тестирования](testing-strategy.md)
- [Отказ от Google](google-migration-roadmap.md)
- [Модель данных и миграционные границы](data-model-and-migrations.md)
- [Курсы, независимые группы, занятия и синонимы задач](courses-groups-and-lessons.md)
- [Принятые технические решения — обновлено 24 июля 2026](accepted-technical-decisions-2026-07.md)
- [Принятые продуктовые UX-решения: проверка, вердикты, реакции и AI](product-ux-decisions-2026-07.md)
- [Рабочий процесс проверки письменных решений](review-workflow.md)
- [Аудитории и устный онлайн-приём](classroom-and-oral-workflow.md)
- [Production deployment](deployment.md)
- [Фазовый план разработки и закрытый опросник](../dev/development-plan/README.md)

Файлы в этой папке фиксируют целевую модель. Реализованный сейчас код — запускаемый каркас и прототип интерфейса; наличие контракта или экрана не означает готовность production-функции.
