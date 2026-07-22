import { createFileRoute } from '@tanstack/react-router'

import { FamilyTaskPage } from '../pages'

export const Route = createFileRoute('/tasks/$taskId')({
  component: FamilyTaskRoute,
})

function FamilyTaskRoute() {
  return <FamilyTaskPage taskId={Route.useParams().taskId} />
}
