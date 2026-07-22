import { createFileRoute } from '@tanstack/react-router'

import { FamilyNotificationsPage } from '../pages'

export const Route = createFileRoute('/profile/notifications')({
  component: FamilyNotificationsPage,
})
