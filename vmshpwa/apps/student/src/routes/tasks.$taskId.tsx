import { createFileRoute } from '@tanstack/react-router'

import { StudentTaskPage } from '../pages'

export const Route = createFileRoute('/tasks/$taskId')({
  component: StudentTaskRoute,
})

function StudentTaskRoute() {
  return <StudentTaskPage taskId={Route.useParams().taskId} />
}
