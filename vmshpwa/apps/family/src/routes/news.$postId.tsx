import { createFileRoute } from '@tanstack/react-router'

import { FamilyNewsDetailPage } from '../pages'

export const Route = createFileRoute('/news/$postId')({
  component: FamilyNewsDetailRoute,
})

function FamilyNewsDetailRoute() {
  return <FamilyNewsDetailPage postId={Route.useParams().postId} />
}
