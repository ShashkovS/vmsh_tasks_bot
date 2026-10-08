import { z } from 'zod'
import { publicIdSchema } from '@vmsh/contracts'

export const historySearchSchema = z.object({
  course: publicIdSchema.optional(),
  lesson: z.coerce.number().int().nonnegative().optional(),
  teacher: publicIdSchema.optional(),
  student: publicIdSchema.optional(),
  problem: publicIdSchema.optional(),
  comment: z.coerce.string().max(500).optional(),
  cursor: publicIdSchema.optional(),
  review: publicIdSchema.optional(),
})
export type HistorySearch = z.infer<typeof historySearchSchema>
