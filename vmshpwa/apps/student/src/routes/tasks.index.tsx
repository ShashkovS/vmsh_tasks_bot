import { createFileRoute } from '@tanstack/react-router'
import { z } from 'zod'

import { StudentTasksPage } from '../pages'

const searchSchema = z.object({
  course: z.string().trim().min(1).optional(),
  group: z.string().trim().min(1).optional(),
  view: z.enum(['list', 'sheet']).catch('list'),
  lesson: z.coerce.number().int().positive().optional(),
  topic: z.string().trim().min(1).optional(),
})

export const Route = createFileRoute('/tasks/')({
  validateSearch: searchSchema,
  component: StudentTasksPage,
})
