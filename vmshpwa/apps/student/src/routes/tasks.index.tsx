import { createFileRoute } from '@tanstack/react-router'
import { z } from 'zod'

import { StudentTasksPage } from '../pages'

const searchSchema = z.object({
  view: z.enum(['list', 'sheet']).catch('list'),
  lesson: z.coerce.number().int().positive().optional(),
  topic: z.string().trim().min(1).optional(),
})

export const Route = createFileRoute('/tasks/')({
  validateSearch: searchSchema,
  component: StudentTasksPage,
})
