import { createFileRoute } from '@tanstack/react-router'

import { StaffGenericPage } from '../pages'

export const Route = createFileRoute('/audit')({
  component: () => (
    <StaffGenericPage
      title="Журнал изменений"
      description="Кто, когда и что изменил: публикации, режим участия, metadata, проверки и рассылки."
    />
  ),
})
