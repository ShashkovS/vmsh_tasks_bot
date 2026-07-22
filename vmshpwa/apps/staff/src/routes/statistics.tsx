import { createFileRoute } from '@tanstack/react-router'

import { StaffGenericPage } from '../pages'

export const Route = createFileRoute('/statistics')({
  component: () => (
    <StaffGenericPage
      title="Статистика"
      description="Уроки, темы, сложность задач, динамика школьников, нагрузка проверки и очное участие."
    />
  ),
})
