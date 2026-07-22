import { createFileRoute } from '@tanstack/react-router'

import { StaffGenericPage } from '../pages'

export const Route = createFileRoute('/classrooms')({
  component: () => (
    <StaffGenericPage
      title="Распределение по аудиториям"
      description="Автораскладка по вместимости и группам, ручной drag-and-drop, публикация и уведомления."
    />
  ),
})
