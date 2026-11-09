# Кнопка обновления PWA — 11 сентября 2026

[Контракт и реализация](../../vmshpwa/docs/runtime-isolation.md#восстановление-кнопки-обновления--11-сентября-2026).

Плашка Workbox сохраняет `needRefresh`, когда worker уже активировался в другой
вкладке. Старый обработчик не находил `registration.waiting`, вызывал
`updateServiceWorker(false)` и завершался без ошибки и без перезагрузки:
`messageSkipWaiting()` при отсутствии ожидающего worker ничего не делает.
Это воспроизводимый сценарий, согласующийся с сообщением пользователя;
состояние его production-браузера непосредственно не исследовалось.

Общий обработчик Student/Family перечитывает регистрацию, активирует ожидающий
worker либо перезагружает текущий URL, если обновление уже активировано.
Устанавливающийся worker ожидается, `controllerchange` не теряется во время
асинхронного поиска регистрации. При неподтверждённой активации через 12 секунд
показывается ошибка и доступен повтор. Двойной запуск блокируется, размонтирование
отменяет ожидание. Сторонняя активация сама по себе не перезагружает текущий ввод.

Проверено:

- **8 unit**: `packages/app-shell/src/pwa-update-activation.test.ts`,
  `apps/student/src/pwa-update.test.tsx`; обычная/поздняя активация, гонка с
  поиском регистрации, установка, таймаут, повтор, ошибка, отмена и состояние кнопки.
- **12 E2E**, без повторов: `e2e/runtime-isolation.spec.ts`, фильтр
  `byte-different built worker`. Student/Family × обычное нажатие / активация
  в другой вкладке × Chromium/WebKit/Firefox. Реальная production-сборка,
  изолированный aiohttp и byte-different `sw.js`, без подмены регистрации.
  Подтверждены настоящая перезагрузка по кнопке с сохранением URL, новая версия
  контролирующего worker, работоспособность при несовместимом runtime и
  сохранение кэшей другого приложения.
- Запуск через `e2e_runner.exclusive_e2e_run` / `run_commands`: `pnpm build`,
  затем `pnpm exec playwright test e2e/runtime-isolation.spec.ts --grep
  'byte-different built worker' --retries=0`.
- TypeScript app-shell/Student/Family и `tsconfig.json`, ESLint, Prettier,
  `git diff --check` и production build прошли.

Владелец разрешил commit/push 11 сентября 2026; серверный выпуск не выполнялся. Сброс регистрации,
очистка черновиков и данных аккаунта не выполняются.
