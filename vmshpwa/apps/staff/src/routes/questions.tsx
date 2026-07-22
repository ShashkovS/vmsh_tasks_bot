import { createFileRoute } from '@tanstack/react-router'

import { StaffGenericPage } from '../pages'

export const Route = createFileRoute('/questions')({
  component: () => (
    <StaffGenericPage
      title="Вопросы школьников"
      description="Общие и привязанные к задачам realtime-треды с историей и вложениями."
    />
  ),
})
