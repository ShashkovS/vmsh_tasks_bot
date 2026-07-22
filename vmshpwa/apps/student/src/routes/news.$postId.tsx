import { createFileRoute } from '@tanstack/react-router'

import { StudentNewsDetailPage } from '../pages'

export const Route = createFileRoute('/news/$postId')({
  component: StudentNewsDetailRoute,
})

function StudentNewsDetailRoute() {
  return <StudentNewsDetailPage postId={Route.useParams().postId} />
}
