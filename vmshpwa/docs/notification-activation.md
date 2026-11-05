# Активация уведомлений — 2026-09-12

Student и Family предлагают включить уведомления в кабинете, когда сервер публикует
доступную VAPID-конфигурацию. Staff и режим тестирования школьника исключены.
Системное разрешение запрашивается только нажатием кнопки. «Не сейчас» сохраняется
для конкретных instance, audience и account. Настройки в профиле остаются доступны.

Реализация: `packages/app-shell/src/push-onboarding.tsx`, `push-device.ts`, корневые
маршруты Student/Family, `packages/product/src/push-device-controls.tsx`.
Существующая подписка сверяется с сервером при входе, возврате фокуса и восстановлении
сети. Успех показывается после подтверждения сервера; ошибка допускает повтор без
повторной подписки. Ожидание service worker ограничено 10 секундами.

На iOS предлагается добавить кабинет на экран «Домой». Требование платформы:
[WebKit](https://webkit.org/blog/13878/web-push-for-web-apps-on-ios-and-ipados/).
Оба `apps/*/src/sw.ts` показывают каждый корректный push независимо от открытых вкладок:
[Apple: userVisibleOnly](https://developer.apple.com/documentation/usernotifications/sending-web-push-notifications-in-web-apps-and-browsers).

`models/pwa/review_notifications.py` направляет в `/student/profile/notifications`.
Маршрут `/student/notifications` перенаправляет туда старые сохранённые уведомления.
Новых таблиц и миграций нет. Существующие категории, настройки, очередь, отложенная
доставка и объединение проверок за 30 минут сохраняются. Секретный VAPID-ключ остаётся
только на сервере; на клиент приходит публичный ключ.

Проверки: `push-device.test.tsx`, `push-onboarding.test.tsx`, `push-browser.test.ts`,
`notification-client.test.ts`; backend — phase8 review notifications, push subscriptions,
push delivery и `test_web_push.py`. Реальную системную доставку на телефоне необходимо
подтвердить после выпуска: браузерные моки не доказывают доставку через Apple/Google.

## Отчёт

16 unit-тестов frontend, 20 backend-тестов и 6 Chromium Storybook-состояний прошли.
Production build прошёл. [Снимок инструкции iOS](push-install-required.png) проверен.
Backend запускался на изолированном aiohttp, без production-получателей.
Typecheck всех приложений и ESLint изменённых компонентов прошли.

## Вход из профиля и восстановление разрешения

`student-profile-page.tsx` и `FamilyProfilePage` в `apps/family/src/pages.tsx`
содержат блок «Уведомления» со ссылкой на существующие настройки.
`PushDeviceControls` в состоянии denied показывает инструкции по браузерам,
возврату в кабинет и повторному подключению.
Источники инструкций: [Chrome](https://support.google.com/chrome/answer/3220216),
[Edge](https://support.microsoft.com/en-us/edge/manage-website-notifications-in-microsoft-edge),
[Firefox](https://support.mozilla.org/en-US/kb/push-notifications-firefox),
[Safari](https://support.apple.com/en-euro/guide/safari/sfri40734/mac),
[iOS](https://webkit.org/blog/13878/web-push-for-web-apps-on-ios-and-ipados/).

## Переход из Android-уведомления

`packages/offline/src/push-notification.ts:openPushNotification` используется обоими SW.
Прямой openWindow в рамках notificationclick заменяет matchAll → navigate → focus:
ожидание навигации фонового клиента могло сорвать открытие. Chrome Android может
переиспользовать установленное PWA: [MDN](https://developer.mozilla.org/en-US/docs/Web/API/Clients/openWindow).
Повторная фокусировка выполняется на возвращённом новом клиенте; её отказ не отменяет
успешную навигацию. URL проверяется после нормализации, чужой audience не открывается.
Unit-регрессии проверяют немедленный вызов openWindow, точный deep link, null/focus failure
и отклонение переходов за пределы audience. Реальный Android требует повторного теста.
