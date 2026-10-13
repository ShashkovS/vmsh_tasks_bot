import { createFileRoute } from '@tanstack/react-router'

import { StaffCapabilityBoundary } from '@vmsh/app-shell'

import { StaffTestAttemptRecheckPage } from '../test-attempt-recheck-page'

export const Route = createFileRoute('/problems/$problemId')({
  component: StaffProblemRoute,
})

function StaffProblemRoute() {
  const { problemId } = Route.useParams()
  return (
    <StaffCapabilityBoundary capability="checker.manage">
      <StaffTestAttemptRecheckPage problemId={problemId} />
    </StaffCapabilityBoundary>
  )
}
