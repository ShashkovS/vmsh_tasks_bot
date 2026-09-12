# Phase 7: production-build E2E распределения и рассылки аудиторий

Дата проверки: 2 августа 2026 года.

## Проверяемый маршрут

Один и тот же сквозной сценарий независимо выполняется в Chromium, WebKit и
Firefox:

1. Admin пересчитывает план отдельного очного события.
2. Ручное изменение аудитории сохраняется в локальном черновике и переживает
   reload.
3. Admin подтверждает план и открывает историю назначений школьника.
4. Admin отдельным действием получает preview рассылки, отключает недоступный в
   E2E Telegram-канал и отправляет назначение только в PWA.
5. Student входит через настоящий экран аутентификации, видит аудиторию и
   отдельное in-app уведомление.
6. Связанный Family-аккаунт видит то же подтверждённое назначение, но его список
   notification events остаётся пустым.
7. Admin скрывает назначенную аудиторию. Student и Family сразу видят состояние
   «Аудитория переназначается», а старое время рассылки не переносится в новое
   состояние.
8. Staff показывает школьника в секции «Не распределены / переназначаются»,
   пересчитывает план и выбирает другую активную аудиторию.
9. Admin подтверждает новый план и только отдельным явным действием выполняет
   вторую PWA-рассылку. Student и Family видят новую аудиторию; Family по-прежнему
   не получает notification event.

## Изоляция

- Каждый browser project использует собственные Student/Family-аккаунты,
  отдельную учебную группу, отдельное очное событие и отдельную аудиторию для
  проверки скрытия. Поэтому три мутационных сценария безопасно идут параллельно
  через одну E2E-БД и не меняют планы друг друга.
- Все браузеры работают с production bundles через одно-origin E2E gateway,
  настоящий aiohttp и отдельную `db/vmshpwa_e2e.sqlite3`.
- MSW, Google, S3, Telegram Bot API и production credentials не используются.
- Telegram transport отдельно проверяется recording-adapter и разрешённым
  live-test harness; browser E2E честно показывает отсутствие Telegram у
  synthetic recipients и отправляет только PWA.

## Результат

```text
make pwa-e2e-classrooms
  Chromium: 3 passed
  WebKit:   3 passed
  Firefox:  3 passed
  total:    9 passed

make pwa-e2e-family
  total:    6 passed
```

Эта команда также успешно собрала Student, Family и Staff production bundles;
Student и Family service workers собраны через `injectManifest`. Visual
snapshots не создавались и не обновлялись. Family-регрессия выполнена отдельно,
поскольку classroom-изоляция добавляет собственные группы тем же Family
fixtures.

## Файлы

- `vmshpwa/scripts/seed_e2e_classrooms.py` — изолированные аккаунты, связи семьи
  и classroom events для трёх браузеров;
- `vmshpwa/e2e/classroom-catalog.spec.ts` — browser flow и пользовательские
  assertions;
- `models/pwa/classroom_public.py` — публичное состояние сбрасывает старый
  `announcedAt`, когда назначенная аудитория больше недоступна;
- `pwa_tests/integration/test_classroom_catalog_http_api.py` — API-регрессия для
  `assigned → reassigning` после скрытия комнаты.

## Что proof не закрывает

- production-size обезличенный rehearsal распределения;
- временный handoff подтверждённого snapshot в legacy-печать;
- ручное визуальное принятие полного planner;
- живую Telegram-сеть: она намеренно не является зависимостью E2E.
