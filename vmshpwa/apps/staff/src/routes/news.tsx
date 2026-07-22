import { createFileRoute } from '@tanstack/react-router'

import { StaffGenericPage } from '../pages'

export const Route = createFileRoute('/news')({
  component: () => (
    <StaffGenericPage
      title="Новости"
      description="Локальные копии Telegram-постов, скрытие, собственные публикации и preview форматирования."
    />
  ),
})
