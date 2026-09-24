import { createFileRoute } from '@tanstack/react-router'

import { StaffLessonsPage } from '../staff-lessons-page'
import { useAuthenticatedPrincipal } from '@vmsh/app-shell'
import { StaffTestingPage } from '../staff-testing-page'

export const Route = createFileRoute('/lessons/')({ component: LessonsRoute })
function LessonsRoute() {
  const principal = useAuthenticatedPrincipal()
  return principal.audience === 'staff' && principal.capabilities.includes('content.manage') ? (
    <StaffLessonsPage />
  ) : (
    <StaffTestingPage />
  )
}
