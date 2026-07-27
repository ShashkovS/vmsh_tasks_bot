import { createFileRoute } from '@tanstack/react-router'

import { StaffLessonContentPage } from '../content-page'

export const Route = createFileRoute('/lessons/$lessonId')({
  component: StaffLessonDetailRoute,
})

function StaffLessonDetailRoute() {
  return <StaffLessonContentPage lessonId={Route.useParams().lessonId} />
}
