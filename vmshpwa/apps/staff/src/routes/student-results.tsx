import { createFileRoute } from '@tanstack/react-router'
import { z } from 'zod'
import { publicIdSchema } from '@vmsh/contracts'
import { StudentResultsPage } from '../student-results-page'

export const Route = createFileRoute('/student-results')({
  validateSearch: z.object({
    student: publicIdSchema.optional().catch(undefined),
    course: publicIdSchema.optional().catch(undefined),
    lesson: z.coerce.number().int().nonnegative().optional().catch(undefined),
  }),
  component: StudentResultsRoute,
})
function StudentResultsRoute() {
  const search = Route.useSearch()
  const navigate = Route.useNavigate()
  return (
    <StudentResultsPage
      search={search}
      onChange={(next, replace) => void navigate({ search: next, replace: replace ?? false })}
    />
  )
}
