import { createFileRoute, redirect } from '@tanstack/react-router'

// Keep previously stored notification links valid without rewriting events.
export const Route = createFileRoute('/notifications')({
  beforeLoad: () => redirect({ to: '/profile/notifications', replace: true }),
})
