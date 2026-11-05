import { createFileRoute } from '@tanstack/react-router'
import { StaffReviewSeriesPage } from '../review-series-page'

export const Route = createFileRoute('/review/series/$problemId')({ component: SeriesRoute })
function SeriesRoute() {
  const { problemId } = Route.useParams()
  return <StaffReviewSeriesPage key={problemId} problemId={problemId} />
}
