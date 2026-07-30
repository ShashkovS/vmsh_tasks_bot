# Phase 7: production-build E2E распределения и рассылки аудиторий

Дата проверки: 30 июля 2026 года.

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

## Изоляция

- Каждый browser project использует собственные Student/Family-аккаунты и
  собственное очное событие.
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
```

Эта команда также успешно собрала Student, Family и Staff production bundles;
Student и Family service workers собраны через `injectManifest`. Visual
snapshots не создавались и не обновлялись.

## Файлы

- `vmshpwa/scripts/seed_e2e_classrooms.py` — изолированные аккаунты, связи семьи
  и classroom events для трёх браузеров;
- `vmshpwa/e2e/classroom-catalog.spec.ts` — browser flow и пользовательские
  assertions.

## Что proof не закрывает

- production-size обезличенный rehearsal распределения;
- временный handoff подтверждённого snapshot в legacy-печать;
- ручное визуальное принятие полного planner;
- живую Telegram-сеть: она намеренно не является зависимостью E2E.
