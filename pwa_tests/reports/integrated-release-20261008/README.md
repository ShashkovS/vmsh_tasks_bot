# Объединённый выпуск ВМШ / TLF — 2026-10-08

[Авторизация, состав, миграции и текущий статус](../../../docs/performance/integrated-release-20261008.md).

Исходные работы сохранены отдельными коммитами и merged в интеграционную ветку.
[Production preflight](preflight.json): current schema 0113, tracked checkout clean,
service-specific credentials/runtime files retained. [TLF deploy script](deploy-tlf.sh)
проверен синтаксически; [перечень controls](deploy-script-review.json).

Общий release gate в работе. Последний полный запуск: format/types/lint/i18n,
2882 Python / 7 SKIP, 1068 frontend, 364 Storybook PASS; основная E2E-фаза
385 PASS / 20 SKIP / 6 FAIL. [Квитанция и contexts](matrix-failures/release-gate.json).
Синхронизация тестов исправлена; [реальная SW активация](sw-real-button.json):
12 PASS в трёх браузерах. Product code и golden snapshots сохранены.
Текущие public smoke: [ВМШ](vmsh-http-before.log), [TLF](tlf-http-before.log).

Production deployment ещё не выполнялся. Direct upload для Beget остаётся disabled.
Квитанции проверки и фактического выпуска будут добавлены после завершения.

Первый общий gate остановлен после подтверждённого reconnect FAIL. Его
[квитанция](initial-release-gate.json) помечена invalid: обнаружена и исправлена
ошибка записи статуса при interruption. Первое предположение о synthetic events
не подтвердилось. После исправления замены старых waves
[reconnect matrix](problem-release-replacement.json): 3 PASS. Временная
диагностика удалена; network-loss assertions и snapshots сохранены. Финальный
общий gate запускается заново.

Интеграционная ветка `codex/integrated-release-20261008` запушена (`d6eb7fa9`).
Финальный all-mode повтор корректно прерван с exit 130;
[resource degradation](resource-degradation.json) и [полные traces](final-navigation-failures/interrupted-gate.json)
не считаются PASS. Остановлены только принадлежащие прогону services/browsers.
Production ветка и оба портала ещё не менялись; остаточный gate/выпуск pending.
