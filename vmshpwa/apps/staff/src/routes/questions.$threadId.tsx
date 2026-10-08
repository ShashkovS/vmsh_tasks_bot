import { createFileRoute } from '@tanstack/react-router'

import { StaffSupportThreadPage } from '../staff-support-pages'

export const Route = createFileRoute('/questions/$threadId')({
  component: StaffQuestionThreadRoute,
})

function StaffQuestionThreadRoute() {
  const { threadId } = Route.useParams()
  return <StaffSupportThreadPage key={threadId} threadId={threadId} />
}
