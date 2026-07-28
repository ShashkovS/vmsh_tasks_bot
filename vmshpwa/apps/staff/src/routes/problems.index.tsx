import { createFileRoute } from '@tanstack/react-router'

import { StaffGenericPage } from '../pages'

export const Route = createFileRoute('/problems/')({
  component: () => (
    <StaffGenericPage
      description="Компактная spreadsheet-поверхность с TSV copy/paste, validation и редактированием checker-кода."
      title="Настройки задач"
    />
  ),
})
