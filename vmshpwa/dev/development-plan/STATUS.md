# Статус плана разработки


## 2026-10-08 — Публичный домен файлов ВМШ

Реализована миграция сохранённых URL на `vmshstor.shashkovs.ru` и синхронизация
deploy/nginx с уже применёнными владельцем production-настройками. Старый
домен сохраняется в CSP; другие бакеты не меняются. План, границы и фактический
production provenance: [решение](../../docs/public-media-domain-20261008.md).
40 целевых тестов, Ruff, schema inventory, format/types/lint/i18n, 1048 frontend,
363 Storybook и 2 Chromium content — PASS; DDL не изменился. Общий Python:
2827 PASS / 8 SKIP; 14 fixture failures устранены восстановлением approved inputs.
Оставшиеся 3 ошибки auth/scope воспроизведены на исходном HEAD, общий gate не
зелёный. [Отчёт](../../../pwa_tests/reports/public-media-domain-20261008/validation.json).
Production data migration ещё не применена.
