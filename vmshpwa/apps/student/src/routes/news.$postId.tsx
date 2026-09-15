import { createFileRoute } from '@tanstack/react-router'

import { StudentNewsPostPage } from '../student-news-page'

export const Route = createFileRoute('/news/$postId')({
  component: StudentNewsDetailRoute,
})

function StudentNewsDetailRoute() {
  return <StudentNewsPostPage postId={Route.useParams().postId} />
}
