import { createFileRoute } from '@tanstack/react-router'

import { StudentNotificationsPage } from '../student-notifications-page'

export const Route = createFileRoute('/profile/notifications')({
  component: StudentNotificationsPage,
})
