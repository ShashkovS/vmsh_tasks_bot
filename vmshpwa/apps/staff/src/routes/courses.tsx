import { createFileRoute } from '@tanstack/react-router'
import { z } from 'zod'

import { StaffCoursesPage } from '../pages'
import { StaffCourseCatalogPage } from '../staff-course-catalog-page'
import { StaffTelegramBindings } from '../telegram-bindings-page'

const searchSchema = z.object({
  course: z.string().trim().min(1).optional(),
  group: z.string().trim().min(1).optional(),
  tab: z.enum(['catalog', 'schedule', 'telegram']).catch('catalog'),
})

export const Route = createFileRoute('/courses')({
  validateSearch: searchSchema,
  component: CoursesRoute,
})

function CoursesRoute() {
  const { tab } = Route.useSearch()

  if (tab === 'catalog') return <StaffCourseCatalogPage />

  return <StaffCoursesPage telegram={<StaffTelegramBindings />} />
}
