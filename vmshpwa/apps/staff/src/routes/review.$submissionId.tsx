import { createFileRoute } from '@tanstack/react-router'

import { ReviewWorkspacePage } from '../pages'

export const Route = createFileRoute('/review/$submissionId')({
  component: ReviewWorkspaceRoute,
})

function ReviewWorkspaceRoute() {
  return <ReviewWorkspacePage submissionId={Route.useParams().submissionId} />
}
