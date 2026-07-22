import { createFileRoute } from '@tanstack/react-router'

import { StaffGenericPage } from '../pages'

export const Route = createFileRoute('/users')({
  component: () => (
    <StaffGenericPage
      title="Участники и группы"
      description="Массовая вставка таблицы, ручное редактирование и управление online/очным режимом."
    />
  ),
})
