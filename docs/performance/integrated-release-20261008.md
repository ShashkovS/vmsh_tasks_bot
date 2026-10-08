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

Статус: объединение завершено; последний общий gate на `68eee3f6`: types/lint/i18n,
2882 Python / 7 SKIP, 1068 frontend и 364 Storybook PASS. Основная E2E-фаза:
385 PASS / 20 SKIP / 6 FAIL. Исправляются test harness и selectors; production
не менялся. Figure/statistics/visual фазы ещё не запускались в этом повторе. Production
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

## Синхронизация E2E после объединения

[Полная квитанция FAIL](../../pwa_tests/reports/integrated-release-20261008/matrix-failures/release-gate.json)
фиксирует неизменный source digest. В Chromium новый полный history повторяет
комментарий preview: [review-workspace](../../vmshpwa/e2e/review-workspace.spec.ts)
проверяет его в конкретном history region. Service worker test ранее принимал
любой installed worker, включая baseline: [runtime-isolation](../../vmshpwa/e2e/runtime-isolation.spec.ts)
теперь ждёт exact requested generation до активации из другой вкладки.
Первое предположение о baseline waiting worker не объяснило Chromium FAIL:
raw postMessage из другой вкладки оставлял worker installed. Сценарий использует
настоящую кнопку «Обновить сейчас» во второй вкладке того же кабинета и ждёт
её настоящую navigation; затем проверяет exact generation первой вкладки,
её stale banner и navigation после собственного update click. Так проверяется
полный пользовательский flow без test-side reload или обхода активации.
WebKit traces показывают зависание холодной navigation на load и гонку
profile reload после записи locale cookie: [auth-personas](../../vmshpwa/e2e/auth-personas.ts)
ждёт DOM и прежние semantic login assertions, [support-dialogue](../../vmshpwa/e2e/support-dialogue.spec.ts)
ждёт реальную main-frame navigation после переключения языка. Product code,
network guard, exact generation assertions и screenshot baselines сохранены.
Focused SW activation: 12 PASS, Chromium/WebKit/Firefox; review clone/correction/move: 3 PASS.
Locale/network/support focused assertions также PASS во всех трёх engines.
Финальный общий gate pending.

## Финальный browser harness и границы квитанции

Повтор default all-mode остановлен со статусом 130 после повторного WebKit
cold-navigation timeout и последующих ошибок `browserContext.newPage` ещё
до выполнения product assertions. [Квитанция и traces](../../pwa_tests/reports/integrated-release-20261008/final-navigation-failures/interrupted-gate.json).
Это не PASS общего all-mode. Non-browser suites вновь PASS.
В [i18n.spec.ts](../../vmshpwa/e2e/i18n.spec.ts) второй device использует общую
secondaryContext fixture с loopback guard, явным baseURL и гарантированным
teardown. Network boundary test открывает реальную Staff login page и ждёт
видимое поле логина перед прежними foreign HTTP/WS probes. Cold root shell
остаётся покрыт shells/authentication tests. Product source после `68eee3f6`
не менялся; timeouts, retries и golden snapshots не ослаблены.

Повтор выполняется отдельными свежими browser phases: support/review/student-results
и release gate `PWA_E2E_MODES="i18n runtime-isolation figure-layout statistics visual"`.
Они завершают затронутые сценарии и оставшиеся destructive/visual фазы;
полный исходный FAIL/interrupt сохраняется в отчёте. Выпуск pending.

## Ресурсы локального окружения и опубликованный результат

Интеграция `d6eb7fa9` опубликована в `codex/integrated-release-20261008`;
`origin/vmshpwa` и оба production остаются на прежних ревизиях. Во время
повтора локальный Mac деградировал: [23/24 GiB, load average 125, 29 stuck processes](../../pwa_tests/reports/integrated-release-20261008/resource-degradation.json).
Стали таймаутиться также ранее проходившие Chromium boot/preparation;
изолированные test services 8380/5380 и тестовые браузеры остановлены.
Изменений product code после `68eee3f6` нет; исходные completed non-browser
PASS и 385/20/6 all-matrix receipt сохранены. Отдельные свежие phases и
оставшиеся figure/statistics/visual не считаются PASS. Предварительный TLF
deploy script скопирован в `/tmp`, SHA-256 совпадает; cutover не запускался.
Следующий шаг: свободные ресурсы и финальный gate либо явно выбранный
владельцем выпуск по уже завершённым проверкам.

## Текущее состояние перед handoff

[Последний focused release receipt](../../pwa_tests/reports/integrated-release-20261008/final-focused-failure/summary.json):
format/types/lint/i18n, 2882 Python / 7 SKIP, 1068 frontend, 364 Storybook PASS;
первая i18n browser phase 24 PASS / 12 FAIL, source_changed=false. Остальные
phases не запущены. Часть FAIL — locale reload, начатый после изменения
`html.lang` и одновременно с navigation. Все восемь journeys
[i18n.spec.ts](../../vmshpwa/e2e/i18n.spec.ts) теперь ждут фактическую
main-frame navigation, DOM и `lang=en`. Formatting/typed ESLint PASS;
[повтор](../../pwa_tests/reports/integrated-release-20261008/locale-reload-fixed-interrupted.json)
дал успешные Chromium journeys, но WebKit вновь зависал на cold boot/teardown
и прерван со статусом 130. Эталонные снимки, assertions, timeout и retries
не ослаблены. Все принадлежащие прогону браузеры и services 8380/5380 остановлены.

**Release gate не зелёный. Оба production ещё не изменены.**
Требуется свободное окружение и завершение финального gate либо отдельное
решение владельца использовать уже выполненные проверки. После этого:
ff-only `vmshpwa`, push через системный SSH-agent, штатный защищённый VMSH
deploy и [подготовленный TLF script](../../pwa_tests/reports/integrated-release-20261008/deploy-tlf.sh)
на том же SHA; затем migration/HTTP/runtime/static/backups verification.
Direct S3 verified flag остаётся false.
