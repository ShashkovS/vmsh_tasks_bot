import { createFileRoute } from '@tanstack/react-router'

import { StaffReviewWorkspacePage } from '../review-workspace-page'

export const Route = createFileRoute('/review/$submissionId')({
  component: ReviewWorkspaceRoute,
})

function ReviewWorkspaceRoute() {
  return <StaffReviewWorkspacePage queueId={Route.useParams().submissionId} />
}
