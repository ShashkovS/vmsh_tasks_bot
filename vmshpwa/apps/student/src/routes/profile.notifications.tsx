import { createFileRoute } from '@tanstack/react-router'

import { StudentNotificationsPage } from '../pages'

export const Route = createFileRoute('/profile/notifications')({
  component: StudentNotificationsPage,
})
