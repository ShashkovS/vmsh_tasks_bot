import { createFileRoute } from '@tanstack/react-router'

import { ProblemImportPage } from '../problem-import-page'

export const Route = createFileRoute('/problems/')({
  component: ProblemImportPage,
})
