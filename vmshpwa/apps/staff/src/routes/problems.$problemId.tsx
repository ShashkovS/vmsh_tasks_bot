import { createFileRoute } from '@tanstack/react-router'

import { StaffGenericPage } from '../pages'

export const Route = createFileRoute('/problems/$problemId')({
  component: StaffProblemRoute,
})

function StaffProblemRoute() {
  return (
    <StaffGenericPage
      title={`Задача ${Route.useParams().problemId}`}
      description="Подробные метаданные, версии, варианты ответа, сообщения и произвольный Python checker."
    />
  )
}
