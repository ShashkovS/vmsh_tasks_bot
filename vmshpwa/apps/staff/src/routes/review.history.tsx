import { createFileRoute } from '@tanstack/react-router'
import { StaffReviewHistoryPage } from '../review-history-page'
import { historySearchSchema } from '../review-history-search'

export const Route = createFileRoute('/review/history')({
  validateSearch: historySearchSchema,
  component: History,
})
function History() {
  const search = Route.useSearch()
  const navigate = Route.useNavigate()
  return (
    <StaffReviewHistoryPage
      search={search}
      onSearch={(next) => void navigate({ search: next, resetScroll: false })}
    />
  )
}
