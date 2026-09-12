import { createFileRoute } from '@tanstack/react-router'
import { OrganizerPage } from '@vmsh/app-shell'
// docs/organizer-questions.md: independent audience route, no student impersonation.
export const Route = createFileRoute('/questions/organizers/')({
  validateSearch: (search: Record<string, unknown>) => ({
    state: ['all', 'answered', 'awaiting_staff'].includes(String(search.state))
      ? String(search.state)
      : 'awaiting_staff',
  }),
  component: Page,
})
function Page() {
  const navigate = Route.useNavigate()
  return (
    <OrganizerPage
      state={Route.useSearch().state}
      onNavigate={(id, _create, state) => {
        if (id) void navigate({ to: '/questions/organizers/$threadId', params: { threadId: id } })
        else
          void navigate({
            to: '/questions/organizers',
            search: { state: state ?? 'awaiting_staff' },
          })
      }}
    />
  )
}
