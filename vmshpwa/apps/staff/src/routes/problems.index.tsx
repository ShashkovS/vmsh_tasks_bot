import { createFileRoute, redirect } from '@tanstack/react-router'

export const Route = createFileRoute('/problems/')({
  beforeLoad: () => redirect({ to: '/courses', search: { tab: 'catalog' } }),
})
