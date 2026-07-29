import { createFileRoute } from '@tanstack/react-router'
import { z } from 'zod'

import { StaffCoursesPage } from '../pages'
import { StaffTelegramBindings } from '../telegram-bindings-page'

const searchSchema = z.object({
  course: z.string().trim().min(1).optional(),
  group: z.string().trim().min(1).optional(),
  tab: z.enum(['catalog', 'schedule', 'telegram']).catch('catalog'),
})

export const Route = createFileRoute('/courses')({
  validateSearch: searchSchema,
  component: () => <StaffCoursesPage telegram={<StaffTelegramBindings />} />,
})
