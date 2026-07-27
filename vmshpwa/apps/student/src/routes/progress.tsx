import { createFileRoute } from '@tanstack/react-router'
import { z } from 'zod'

import { StudentProgressPage } from '../pages'

const searchSchema = z.object({
  course: z.string().trim().min(1).optional(),
  tab: z.enum(['overview', 'activity', 'achievements']).catch('overview'),
})

export const Route = createFileRoute('/progress')({
  validateSearch: searchSchema,
  component: StudentProgressPage,
})
