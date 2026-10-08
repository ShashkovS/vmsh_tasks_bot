# Объединённый выпуск ВМШ и TLF — 8 октября 2026

Владелец разрешил объединить четыре доработки, прогнать тесты, закоммитить,
запушить и выпустить один результат на оба production портала.

## Состав и сохранение исходников

Исходный head: `55ed5e9c`. Перед изменениями сохранены бинарные patches,
незакоммиченные файлы и SHA-256 manifests в локальной `.runtime/integrate-20261008/source-snapshots`.
Все три исходных worktree были idle; другие ветки и активная Zoom-работа вне scope.

- `0d8f0d73`: [браузерные изображения](browser-image-uploads.md),
  [shared uploader](../../vmshpwa/packages/app-shell/src/image-upload-client.ts).
- `7a97624e`: [полная переписка проверок](../../vmshpwa/docs/review-history.md),
  [проекция истории](../../models/pwa/review_conversation.py).
- `0d5e46f2`: [публичный домен](../../vmshpwa/docs/public-media-domain-20261008.md).
- `b9656500`: [надёжность и производительность](2026-10-08-fixes.md).

Неприменённые новые migrations перенумерованы в единую зависимую цепочку:
[0114](../../migrations/0114.browser_image_uploads.py) →
[0115](../../migrations/0115.vmsh_public_media_domain.py) →
[0116](../../migrations/0116.notification_push_candidate_index.py).
Schema fixtures и ожидаемые heads обновляются из реальной объединённой схемы.

## Проверка и выпуск

Статус: объединение завершено; types/lint/i18n, 2880 Python / 7 SKIP,
1066 frontend и 364 Storybook PASS. Полная E2E-матрица в работе. Production
preflight подтвердил head 0113 на обоих серверах: на ВМШ 6486 старых media
URL, на TLF — 0; настроенный TLF toolchain соответствует закреплённому.
[Guarded TLF script](../../pwa_tests/reports/integrated-release-20261008/deploy-tlf.sh)
подготовлен с online-copy up/down/up rehearsal, проверкой всех product rows,
backups, health, atomic static activation и сохранением credentials/NATS.
Он ещё не запускался.
Точная квитанция общего gate, source digest, public smoke, backups и runtime
heads будут добавлены после фактических проверок. Прежние отдельные PASS/FAIL
не заменяют проверку объединённого результата.

Direct upload остаётся disabled для Beget: провайдер не доказал SHA-256/HEAD
checksum. Современные браузеры используют подготовленный WebP через лёгкий
proxy без повторного кодирования. Production credentials, course settings,
личные ответы и материалы не переносятся из тестовой среды.

## Исходный E2E FAIL и восстановление связи

Первый общий gate прерван после Chromium problem-release reconnect FAIL.
Все non-browser suites PASS. Перестановка synthetic online events не устранила
сбой и отменена. Временная диагностика показала: завершающийся service probe
посылал ready уже после перехода устройства offline; новая общая resync начинала
cache-only reads и могла поглотить следующий настоящий online event. Одного
запрета новых waves при offline оказалось недостаточно: Firefox воспроизвёл
перекрытие с предыдущим чтением. Теперь
[`RealtimeProvider`](../../vmshpwa/packages/app-shell/src/realtime.tsx) отмечает
реальный offline/online переход, а
[`query-resync.ts`](../../vmshpwa/packages/app-shell/src/query-resync.ts) один раз
отменяет запросы прошлой волны, дожидается её завершения и повторно собирает
активные queries. Обычные WS/service-ready события присоединяются к новой волне.
Лимит четырёх сохраняется; offline и replacement regressions, включая abort,
queued queries и logout — 5 frontend PASS. Диагностический код полностью удалён. Assertions, pixel
thresholds и golden snapshots не менялись.

При остановке выявлена отдельная ошибка gate receipt: KeyboardInterrupt мог
сохранить zero предыдущей suite. [`check_runner.py`](../../vmshpwa/scripts/check_runner.py)
теперь фиксирует interruption=130 и не наследует PASS при launcher exception;
две регрессии в [`test_check_optimization.py`](../../pwa_tests/test_check_optimization.py) PASS.
Исходный trace/FAIL и оригинальная ошибочная квитанция сохранены с явной
пометкой invalid в [отчёте](../../pwa_tests/reports/integrated-release-20261008/README.md).
Focused reconnect: Chromium/WebKit/Firefox — 3 PASS. Дополнительно waiters
следуют новой волне перед обработкой следующей invalidation. Полный повтор
release gate на окончательных исходниках pending.
