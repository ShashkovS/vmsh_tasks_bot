# Phase 9: production-build E2E личного прогресса

Дата проверки: 2026-07-30.

## Проверяемый маршрут

Сценарий устного приёма после настоящей записи результата продолжает путь
школьника:

1. Student снова видит задачу как зачтённую.
2. Student открывает `/student/progress` с явным course search parameter.
3. Экран получает сводку из настоящего aiohttp/SQLite API.
4. Строка конкретного занятия показывает одну зачтённую задачу из одной.
5. Teacher записывает более позднее исправление «не зачтено» по той же устной
   задаче.
6. После нового чтения из SQLite Student видит `0 зачтено из 1`.
7. Экран явно сообщает об отсутствии рейтинга и сравнений, а JSON API не
   содержит cohort distribution, percentile, rank или student marker.

Каждый browser project использует своё занятие и результат, поэтому проверки
Chromium, WebKit и Firefox не зависят друг от друга.

## Автоматические доказательства

```text
make pwa-e2e-oral
  Chromium: pass
  WebKit:   pass
  Firefox:  pass
  total:    3 passed
```

Сценарий работает с production-сборками, настоящим aiohttp и отдельной
`db/vmshpwa_e2e.sqlite3`; MSW и production credentials не используются.
Групповые сравнения отсутствуют всегда, а не только скрываются на время grace
period. Snapshots не создавались и не обновлялись.
