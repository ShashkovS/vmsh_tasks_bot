import { createFileRoute } from '@tanstack/react-router'

import { FamilyNewsPostPage } from '../family-news-page'

export const Route = createFileRoute('/news/$postId')({
  component: FamilyNewsDetailRoute,
})

function FamilyNewsDetailRoute() {
  return <FamilyNewsPostPage postId={Route.useParams().postId} />
}
