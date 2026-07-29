import { createFileRoute } from '@tanstack/react-router'
import { z } from 'zod'

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
  return (
    <StaffNewsPage
      onStateChange={(state) => void navigate({ search: { state }, replace: true })}
      state={search.state}
    />
  )
}
