import { createFileRoute } from '@tanstack/react-router'

import { StaffLessonContentPage } from '../content-page'
import { useAuthenticatedPrincipal } from '@vmsh/app-shell'
import { StaffTestingPage } from '../staff-testing-page'

export const Route = createFileRoute('/lessons/$lessonId')({
  component: StaffLessonDetailRoute,
})

function StaffLessonDetailRoute() {
  const principal = useAuthenticatedPrincipal()
  const { lessonId } = Route.useParams()
  return principal.audience === 'staff' && principal.capabilities.includes('content.manage') ? (
    <StaffLessonContentPage lessonId={lessonId} />
  ) : (
    <StaffTestingPage />
  )
}
