import { createFileRoute } from '@tanstack/react-router'

import { FamilyNotificationsPage } from '../family-notifications-page'

/* Phase 8 Family notification settings: dev/design-system/05-pages-and-flows.md. */
export const Route = createFileRoute('/profile/notifications')({
  component: FamilyNotificationsPage,
})
