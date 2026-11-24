# Даты, приём и блоки

## Перенести дедлайн

Вызовите `lesson_window`, сверьте groupLessonId, дату и businessTimezone.
Передайте в `set_submission_cutoff` полученный etag, новую submissionClosesLocalTime,
businessTimezone и confirmChange=true. Снова прочтите окно и проверьте время.
Для повторного открытия задайте будущий дедлайн и проверьте также время начала приёма.

## Показать блок вместе с занятием

Прочитайте `lesson_blocks`. Для новой позиции используйте ETag `"none"`.
Вызовите `save_lesson_block` для before или after с полем markdown.
Прикрепите PDF через `upload_block_pdf`. Для видео используйте отдельный абзац
`::video[Разбор](https://youtu.be/dQw4w9WgXcQ)`. Для сохранённой revisionId
вызовите `publish_lesson_block` с mode=with_lesson и scheduledAt=null.
Прочитайте `lesson_state`, после выпуска занятия проверьте published.revisionId блока и ученический листок.

## Скрыть материал по времени

В `schedule_hide` передайте цель, время ISO 8601 со смещением, ID и версию
опубликованного объекта. Для первого таймера event_version=0. Для переноса
используйте текущую версию события, для отмены передайте due=null.
Проверьте hideEvents в `lesson_state`. Событие хранит конкретную публикацию.
После замены материала старый таймер получает состояние superseded.

[Планировщик](../../../admin_mcp/schedule.py) · [Блоки Staff](../../../apps/pwa_api/lesson_block_routes.py).

Для немедленного закрытия вызовите `set_intake` с opened=false и ETag окна.
Для повторного открытия укажите opened=true и будущий until_local в зоне занятия.
Ответ содержит новое окно, intakeOpen и ближайшие события.
