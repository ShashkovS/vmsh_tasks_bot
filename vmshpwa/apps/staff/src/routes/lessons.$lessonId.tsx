import { createFileRoute } from '@tanstack/react-router'

import { StaffLessonDetailPage } from '../pages'

export const Route = createFileRoute('/lessons/$lessonId')({
  component: StaffLessonDetailRoute,
})

function StaffLessonDetailRoute() {
  return <StaffLessonDetailPage lessonId={Route.useParams().lessonId} />
}
