import { createFileRoute } from '@tanstack/react-router'
import { reviewSheetSearchSchema } from '@vmsh/contracts'
import { StaffReviewSheetPage } from '../review-sheet-page'

// docs/review-sheet.md; design-system/05-pages-and-flows.md § Written review.
export const Route = createFileRoute('/review/sheet')({
  validateSearch: reviewSheetSearchSchema,
  component: SheetRoute,
})
function SheetRoute() {
  const search = Route.useSearch()
  const navigate = Route.useNavigate()
  return (
    <StaffReviewSheetPage
      search={search}
      onSearchChange={(next) => void navigate({ search: next })}
    />
  )
}
