# Диагностика отказа фотографии — 13 ноября 2026

Проверено read-only по обращению с request ID
`8c286a6404a64724ba90bea11caf97c6`.

- Обращение найдено на ВМШ; серверное время обращения —
  `2026-11-13T16:06:36.406454Z`.
- Связанный черновик создан `2026-11-12T14:14:16.946939Z`, остаётся в
  `draft` с нулём сохранённых вложений. Access log содержит POST attachments
  этого черновика `2026-11-12 14:14:17 UTC`: HTTP 422, Safari/macOS.
- [`written_submission_routes.py`](../../../apps/pwa_api/written_submission_routes.py)
  формирует `written_attachment_conversion_failed` только при
  `AssetConversionError`; ошибка относится к обработке фотографии, а не
  условиям приёма задачи. [`observability.ts`](../../../vmshpwa/packages/app-shell/src/observability.ts)
  показывает для сохранённого outbox label общий текст про условия приёма,
  теряя исходное сообщение. [`written-submission-outbox.ts`](../../../vmshpwa/packages/offline/src/written-submission-outbox.ts)
  сохраняет только status/code/requestId, без details.reason/capability.
- По точному request ID journald не содержит записи, в том числе при поиске
  с 1 ноября. Expected API failures не логируются middleware; request trace
  сохраняет только запросы от 200 ms. Raster conversion failure не сохраняет
  stderr. Поэтому точный decoder error по имеющимся журналам не установлен.
- Место и inodes доступны, PWA active/NRestarts=0, ImageMagick объявляет HEIC
  read support; свежие чужие фото успешно конвертируются. Это не доказывает
  исправность обработки конкретного пользовательского файла.
- Исходник ошибочного вложения сервером не сохранён:
  [`written_attachments.py`](../../../helpers/pwa/written_attachments.py)
  вызывает storage.put только после успешной конвертации.

Для воспроизведения нужен исходный файл фотографии; формат текущей
неудачной фотографии неизвестен. Временный обход — экспорт копии в JPEG
и прикрепление её заново (с сохранением исходника для диагностики).
Ученику сообщений не отправляли, данные и production code не менялись.

Возможный последующий scope после воспроизведения: исправить decoder path
по фактической причине; независимо убрать неверный текст для
`written_attachment_conversion_failed` и добавить ограниченные серверные
diagnostics с request ID и reason/capability без содержимого фото.
