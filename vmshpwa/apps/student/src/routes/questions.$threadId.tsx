import { createFileRoute } from '@tanstack/react-router'

import { StudentSupportThreadPage } from '../student-support-pages'

export const Route = createFileRoute('/questions/$threadId')({
  component: StudentQuestionThreadRoute,
})

function StudentQuestionThreadRoute() {
  const { threadId } = Route.useParams()
  return <StudentSupportThreadPage key={threadId} threadId={threadId} />
}
