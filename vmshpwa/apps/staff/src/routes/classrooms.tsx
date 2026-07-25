import { createFileRoute } from '@tanstack/react-router'
import { z } from 'zod'

import { StaffClassroomsPage } from '../pages'

const searchSchema = z.object({
  lesson: z.coerce.number().int().positive().catch(41),
  tab: z.enum(['catalog', 'groups', 'students']).catch('catalog'),
  roomStatus: z.enum(['active', 'archived', 'all']).catch('active'),
})

export const Route = createFileRoute('/classrooms')({
  validateSearch: searchSchema,
  component: ClassroomsRoute,
})

function ClassroomsRoute() {
  const search = Route.useSearch()
  const navigate = Route.useNavigate()
  return (
    <StaffClassroomsPage
      onTabChange={(tab) => void navigate({ search: (current) => ({ ...current, tab }) })}
      tab={search.tab}
    />
  )
}
