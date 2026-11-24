# Ответы и перепроверка

В `search_problems` укажите обозначение, заголовок или фрагмент условия.
Сверьте courseId, groupId и lessonId. Для `group_answers` передайте group_id и
список публичных ID задач одной группы. Повторяйте чтение с nextAfterStudentId
до конца. Участник без отправок получает submitted=false. Для файла письменной
отправки используйте caseId и attachmentId в `read_answer_attachment`.

Чтобы исправить ответ, получите `metadata_grid` для действующей ревизии.
В `edit_metadata` используйте целочисленный problemId строки, patches, ETag и
предварительный просмотр. После сохранения вызовите `preview_recheck` с публичным
ID задачи и сверьте затронутые попытки. В `recheck_problem` передайте полученную
problemRevision и schemaVersion=1. Проверьте ответы группы повторным чтением.
Письменная и устная работа требуют оценки преподавателя.

[Выборки ответов](../../../admin_mcp/results.py) · [Штатная перепроверка](../../../apps/pwa_api/submission_routes.py).
