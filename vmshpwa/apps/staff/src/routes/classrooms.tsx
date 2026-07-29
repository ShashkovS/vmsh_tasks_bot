import { createFileRoute } from '@tanstack/react-router'
import { z } from 'zod'

import { StaffClassroomCatalog } from '../classroom-catalog-page'
import { StaffClassroomAssignments } from '../classroom-assignment-page'
import { StaffClassroomLayout } from '../classroom-layout-page'
import { StaffClassroomsPage } from '../pages'

const searchSchema = z.object({
  event: z.string().trim().min(1).catch('in-person-2026-02-01'),
  course: z.string().trim().min(1).optional(),
  group: z.string().trim().min(1).optional(),
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
      catalog={
        <StaffClassroomCatalog
          onStatusFilterChange={(roomStatus) =>
            void navigate({ search: (current) => ({ ...current, roomStatus }) })
          }
          statusFilter={search.roomStatus}
        />
      }
      layout={<StaffClassroomLayout eventPublicId={search.event} />}
      onTabChange={(tab) => void navigate({ search: (current) => ({ ...current, tab }) })}
      students={<StaffClassroomAssignments eventPublicId={search.event} />}
      tab={search.tab}
    />
  )
}
