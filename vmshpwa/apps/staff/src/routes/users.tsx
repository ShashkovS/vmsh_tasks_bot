import { createFileRoute } from '@tanstack/react-router'
import { z } from 'zod'

import { StaffStudentDirectoryPage } from '../staff-student-directory-page'

const searchSchema = z.object({
  q: z.string().trim().max(100).optional().catch(undefined),
  student: z.string().trim().min(1).optional(),
  course: z.string().trim().min(1).optional(),
})

export const Route = createFileRoute('/users')({
  validateSearch: searchSchema,
  component: UsersRoute,
})

function UsersRoute() {
  const search = Route.useSearch()
  const navigate = Route.useNavigate()
  return (
    <StaffStudentDirectoryPage
      onSearchChange={(next) =>
        void navigate({
          replace: true,
          search: {
            ...(next.query ? { q: next.query } : {}),
            ...(next.studentId ? { student: next.studentId } : {}),
            ...(next.courseId ? { course: next.courseId } : {}),
          },
        })
      }
      search={{
        query: search.q ?? '',
        ...(search.student ? { studentId: search.student } : {}),
        ...(search.course ? { courseId: search.course } : {}),
      }}
    />
  )
}
