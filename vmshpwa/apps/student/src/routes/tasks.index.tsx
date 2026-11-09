import { createFileRoute } from '@tanstack/react-router'

import { StudentTasksArchivePage } from '../student-tasks-page'
import { studentTasksSearchSchema } from '../student-tasks-view'

export const Route = createFileRoute('/tasks/')({
  validateSearch: studentTasksSearchSchema,
  component: StudentTasksRoute,
})

function StudentTasksRoute() {
  return <StudentTasksArchivePage search={Route.useSearch()} />
}
