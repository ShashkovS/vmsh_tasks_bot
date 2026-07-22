import { createFileRoute } from '@tanstack/react-router'

import { StaffGenericPage } from '../pages'

export const Route = createFileRoute('/oral')({
  component: () => (
    <StaffGenericPage
      title="Устные задачи"
      description="Поиск школьника, быстрые отметки и история устных ответов; видеосвязь остаётся в Zoom."
    />
  ),
})
