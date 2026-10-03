# Phase 11: live-проверка локальных конвертеров и test adapters

Дата: 30 июля 2026 года. Все внешние операции выполнялись только с
синтетическими данными и только в заранее выделенных test-контурах.

## Конвертеры

Agent-профиль успешно выполнил полный локальный smoke:

- TikZ → PDF через указанный владельцем
  `/Users/sergeyshashkov/bin/pdflatex`;
- PDF → SVG через `pdf2svg`;
- raster normalization через ImageMagick;
- raster → WebP через `cwebp`;
- установленный ImageMagick объявляет поддержку HEIC decode.

Результат: `ready=true`; временный каталог удалён после проверки. Путь
пользовательского `pdflatex` передавался как локальная environment-настройка и
не зашит в runtime-код или Makefile.

## NATS

Пользовательский NATS, запущенный ранее, к моменту проверки уже не слушал порт
`4222`. Для smoke был временно запущен локальный `nats-server 2.14.3`; после
теста остановлен тем же процессом.

Проверены два subscriber одного одноразового `vmshpwa_agent_smoke_*` prefix и
отдельный изолированный prefix. Оба нужных subscriber получили событие,
изолированный не получил. Результат: `1 passed`.

## Выделенный test S3

Все ключи находились под отдельными `integration/phase11-20260730-*` prefixes.
Для каждой операции cleanup завершился подтверждённым delete ACK.

- базовый put/private read/public GET/delete: passed;
- TikZ → SVG → S3 → private/public read → delete: passed;
- raster → WebP → S3 → private/public read → delete: passed;
- письменное WebP с canonical
  `sol_imgs/user_{id}/{year}/lesson_{n}/{problem}_{time}_{uuid}.webp` shape:
  passed.

Safe provider identity: endpoint host `s3.ru1.storage.beget.cloud`, region
`ru1`, test bucket fingerprint `993fe1242fb7`. Bucket name, access key, secret,
полные object keys и URL в отчёт не записывались.

## Приватный Telegram test-channel

Через ранее проверенный binding тестового бота выполнены два lifecycle:

- обычное сообщение: send → edit → delete;
- rich сообщение/медиа: send → edit → delete всех созданных сообщений.

Оба smoke завершились успешно. Safe runtime reports находятся только в ignored
owner-only каталоге `.runtime/vmshpwa/telegram-smoke/`; token, текст ответа Bot
API, chat title и message IDs не коммитятся. Polling/webhook не запускались.

## Исторические Telegram-сценарии

Отдельная команда `make telegram-history-test` выполнила 44 сценария legacy
бота: правила тестовых ответов, пользовательские handler flows и недельные
admin-операции. Результат: `44 passed`. Набор использует test wiring и не
запускает polling/webhook и не обращается к Telegram API.

## Граница доказательства

Этот proof подтверждает локальный toolchain, текущий Beget test bucket,
публичное чтение тестовых объектов, локальный NATS и test Telegram adapter. Он
не заменяет будущую проверку под production service account на Hetzner и не
является разрешением использовать production credentials в тестах.
