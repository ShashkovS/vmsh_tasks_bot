# Design-system status


## 2026-10-08 — Публичный домен файлов ВМШ

Реализована синхронизация deploy/nginx с production-настройками владельца:
новый media origin `vmshstor.shashkovs.ru`, совместимость старых ссылок и
миграция сохранённых документов без изменений рисунков/разметки. План и
свидетельства владельца: [решение](../../docs/public-media-domain-20261008.md).
40 целевых тестов, schema inventory, format/types/lint/i18n, 1048 frontend,
363 Storybook и 2 Chromium content — PASS. Три оставшиеся ошибки общего Python
воспроизведены на исходном HEAD; [отчёт](../../../pwa_tests/reports/public-media-domain-20261008/validation.json).
Production data migration ещё не применена.
