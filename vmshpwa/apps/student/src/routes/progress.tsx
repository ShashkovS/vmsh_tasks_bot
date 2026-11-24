import { createFileRoute } from '@tanstack/react-router'
import { z } from 'zod'

import { StudentProgressPage } from '../student-progress-page'

const searchSchema = z.object({
  course: z.string().trim().min(1).optional(),
  tab: z.enum(['overview', 'activity', 'achievements']).catch('overview'),
})

export const Route = createFileRoute('/progress')({
  validateSearch: searchSchema,
  component: StudentProgressRoute,
})

function StudentProgressRoute() {
  const search = Route.useSearch()
  const navigate = Route.useNavigate()
  return (
    <StudentProgressPage
      {...(search.course === undefined ? {} : { courseId: search.course })}
      onCourseChange={(course) =>
        void navigate({ search: (previous) => ({ ...previous, course }), replace: true })
      }
    />
  )
}
