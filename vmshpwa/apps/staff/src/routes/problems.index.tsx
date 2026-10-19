import { createFileRoute } from '@tanstack/react-router'

import { StaffCapabilityBoundary } from '@vmsh/app-shell'

import { ProblemImportPage } from '../problem-import-page'

export const Route = createFileRoute('/problems/')({
  component: StaffProblemImportRoute,
})

function StaffProblemImportRoute() {
  return (
    <StaffCapabilityBoundary capability="checker.manage">
      <ProblemImportPage />
    </StaffCapabilityBoundary>
  )
}
