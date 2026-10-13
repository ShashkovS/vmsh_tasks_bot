import { createFileRoute } from '@tanstack/react-router'
import { OrganizerPage } from '@vmsh/app-shell'
// docs/organizer-questions.md: independent audience route, no student impersonation.
export const Route = createFileRoute('/organizers/')({
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
      onNavigate={(id, create, state) => {
        if (id) void navigate({ to: '/organizers/$threadId', params: { threadId: id } })
        else if (create) void navigate({ to: '/organizers/new' })
        else void navigate({ to: '/organizers', search: { state: state ?? 'awaiting_staff' } })
      }}
    />
  )
}
