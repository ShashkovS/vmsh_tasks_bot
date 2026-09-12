import { createFileRoute } from '@tanstack/react-router'
import { LiveMarkingPage } from '../live-marking-page'
import { liveSearchSchema } from '../live-marking-state'

export const Route = createFileRoute('/in-person')({
  validateSearch: liveSearchSchema,
  component: Page,
})
function Page() {
  const search = Route.useSearch()
  const navigate = Route.useNavigate()
  return (
    <LiveMarkingPage
      mode="school"
      search={search}
      onSearch={(next) => {
        void navigate({ search: next })
      }}
    />
  )
}
