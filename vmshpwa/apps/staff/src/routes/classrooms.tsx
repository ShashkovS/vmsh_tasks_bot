import { createFileRoute } from '@tanstack/react-router'
import type { ReactNode } from 'react'
import { z } from 'zod'

import { StaffClassroomCatalog } from '../classroom-catalog-page'
import { StaffClassroomAssignments } from '../classroom-assignment-page'
import { StaffClassroomEventManager } from '../classroom-event-page'
import { StaffClassroomLayout } from '../classroom-layout-page'
import { StaffClassroomsPage } from '../pages'

const searchSchema = z.object({
  event: z.string().trim().min(1).optional(),
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
  const selectEvent = (event: string | undefined) =>
    void navigate({ search: (current) => ({ ...current, event }) })
  const selectEventFirst = (content: (eventPublicId: string) => ReactNode): ReactNode =>
    search.event ? (
      content(search.event)
    ) : (
      <p className="rounded-md border border-border bg-surface p-4 text-small text-muted-foreground">
        Создайте или выберите очное занятие выше.
      </p>
    )
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
      event={
        <StaffClassroomEventManager
          onEventChange={selectEvent}
          selectedEventPublicId={search.event}
        />
      }
      layout={selectEventFirst((eventPublicId) => (
        <StaffClassroomLayout eventPublicId={eventPublicId} />
      ))}
      onTabChange={(tab) => void navigate({ search: (current) => ({ ...current, tab }) })}
      students={selectEventFirst((eventPublicId) => (
        <StaffClassroomAssignments eventPublicId={eventPublicId} />
      ))}
      tab={search.tab}
    />
  )
}
