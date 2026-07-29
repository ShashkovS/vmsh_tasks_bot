import { createFileRoute } from '@tanstack/react-router'
import { z } from 'zod'

import { StaffCoursesPage } from '../pages'
import { StaffCourseCatalogPage } from '../staff-course-catalog-page'
import { StaffCourseSchedulePage } from '../staff-course-schedule-page'
import { StaffTelegramBindings } from '../telegram-bindings-page'

const searchSchema = z.object({
  course: z.string().trim().min(1).optional(),
  group: z.string().trim().min(1).optional(),
  tab: z.enum(['catalog', 'schedule', 'telegram']).catch('catalog'),
})

export const Route = createFileRoute('/courses')({
  validateSearch: searchSchema,
  component: CoursesRoute,
})

function CoursesRoute() {
  const search = Route.useSearch()
  const navigate = Route.useNavigate()

  if (search.tab === 'catalog') return <StaffCourseCatalogPage />

  if (search.tab === 'schedule') {
    return (
      <StaffCourseSchedulePage
        onCourseChange={(course) =>
          void navigate({ search: { ...search, course, group: undefined }, replace: true })
        }
        onGroupChange={(group) => void navigate({ search: { ...search, group }, replace: true })}
        {...(search.course === undefined ? {} : { requestedCourseId: search.course })}
        {...(search.group === undefined ? {} : { requestedGroupId: search.group })}
      />
    )
  }

  return <StaffCoursesPage telegram={<StaffTelegramBindings />} />
}
