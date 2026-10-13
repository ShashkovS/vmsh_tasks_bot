import { createFileRoute } from '@tanstack/react-router'
import { z } from 'zod'
import { useAuthenticatedPrincipal } from '@vmsh/app-shell'
import { StaffTestingPage } from '../staff-testing-page'

import { StaffNewsPage } from '../staff-news-page'

const searchSchema = z.object({
  state: z.enum(['all', 'visible', 'manual_hidden', 'source_deleted']).catch('all'),
})

export const Route = createFileRoute('/news')({
  validateSearch: searchSchema,
  component: StaffNewsRoute,
})

function StaffNewsRoute() {
  const search = Route.useSearch()
  const navigate = Route.useNavigate()
  const principal = useAuthenticatedPrincipal()
  if (principal.audience !== 'staff' || !principal.capabilities.includes('broadcast.manage')) {
    return <StaffTestingPage view="news" />
  }
  return (
    <StaffNewsPage
      onStateChange={(state) => void navigate({ search: { state }, replace: true })}
      state={search.state}
    />
  )
}
