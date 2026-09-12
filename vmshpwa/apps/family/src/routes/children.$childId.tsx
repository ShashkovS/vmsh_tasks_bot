import { createFileRoute } from '@tanstack/react-router'

import { FamilyChildPage } from '../family-children-page'

export const Route = createFileRoute('/children/$childId')({
  component: FamilyChildRoute,
})

function FamilyChildRoute() {
  return <FamilyChildPage childId={Route.useParams().childId} />
}
