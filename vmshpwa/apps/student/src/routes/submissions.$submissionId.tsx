import { createFileRoute } from '@tanstack/react-router'

import { StudentSubmissionPage } from '../pages'

export const Route = createFileRoute('/submissions/$submissionId')({
  component: StudentSubmissionRoute,
})

function StudentSubmissionRoute() {
  return <StudentSubmissionPage submissionId={Route.useParams().submissionId} />
}
