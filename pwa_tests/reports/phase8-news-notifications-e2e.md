# Phase 8: production-build E2E новостей и уведомлений

Дата проверки: 30 июля 2026 года.

## Проверяемые маршруты

Один изолированный сценарий Student и один сценарий Family независимо выполнены
в Chromium, WebKit и Firefox.

Student:

1. Входит через настоящий экран аутентификации.
2. Видит активный групповой баннер, скрывает его и после reload не получает его
   повторно в пределах своей локальной версии баннера.
3. Открывает Telegram-origin публикацию из реального aiohttp news feed.
4. После полного reload с отключёнными Student API читает ту же публикацию из
   account-scoped IndexedDB; shell обслуживает production Service Worker.
5. Открывает реальный список notification events. Видимое непрочитанное событие
   получает серверный read acknowledgement, теряет бейдж «Новое» и исчезает из
   `unreadOnly`-выборки.
6. Для включённой VAPID capability получает явное состояние текущего браузера:
   предложение включить push, активную подписку, отказ браузера либо штатную
   ошибку настройки. Firefox headless в проверенном окружении использовал
   последний вариант.

Family:

1. Видит тот же course-owned пост и доступный через ребёнка групповой баннер.
2. Открывает detail публикации.
3. Получает собственное account-scoped news event с Family route.

## Изоляция

- На каждый browser project созданы отдельные Student/Family accounts и
  notification events.
- `seed_e2e_news.py` пишет маленький детерминированный fixture прямыми SQLite
  запросами до запуска aiohttp; production storage/model код не подменяется.
- Браузеры работают с production bundles, одним loopback origin, настоящим
  aiohttp и отдельной `db/vmshpwa_e2e.sqlite3`.
- MSW, Google, Telegram Bot API, внешние URL и production credentials не
  используются.
- Публичный VAPID key синтетический; private key отсутствует, поэтому E2E не
  запускает внешнюю Web Push доставку.

## Результат

```text
make pwa-e2e-news
  Chromium: 2 passed
  WebKit:   2 passed
  Firefox:  2 passed
  total:    6 passed
```

Команда также успешно собрала все три production bundle; Student и Family
service workers собраны через `injectManifest`. Visual snapshots не создавались
и не обновлялись.

Дополнительные проверки:

```text
uv run pytest -q -n0 pwa_tests/test_e2e_runner.py
  8 passed

pnpm typecheck
  passed for all workspace projects

make pwa-e2e-classrooms
  9 passed; Family still receives no classroom-assignment event when news events coexist
```

## Файлы

- `vmshpwa/scripts/seed_e2e_news.py` — Telegram-origin post, banner и
  account-scoped events;
- `vmshpwa/e2e/news-notifications.spec.ts` — Student/Family browser flows;
- `vmshpwa/playwright.config.ts` — seed startup и синтетическая public VAPID
  capability;
- `vmshpwa/scripts/e2e_runner.py`, `vmshpwa/package.json`, `Makefile` — отдельная
  lock-aware команда `make pwa-e2e-news`.

## Что proof не закрывает

- реальную доставку Web Push на установленное физическое устройство;
- живой Telegram ingest: он проверяется отдельным разрешённым test-bot harness;
- inventory уже запланированных вручную Telegram-публикаций;
- итоговый Staff delivery-counter и ручное visual acceptance.
