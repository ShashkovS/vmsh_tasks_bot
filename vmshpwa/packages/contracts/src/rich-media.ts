import { z } from 'zod'

import { richHttpsUrlSchema } from './rich-document'

/** Response from the shared Staff upload control used by news and broadcasts. */
export const staffRichMediaImageSchema = z
  .object({
    url: richHttpsUrlSchema,
    mimeType: z.literal('image/webp'),
    width: z.number().int().positive().max(1_920),
    height: z.number().int().positive().max(1_920),
  })
  .strip()
export type StaffRichMediaImage = z.infer<typeof staffRichMediaImageSchema>

export const staffRichMediaUploadResponseSchema = z
  .object({
    schemaVersion: z.literal(1),
    image: staffRichMediaImageSchema,
    requestId: z.string().min(1),
  })
  .strip()
export type StaffRichMediaUploadResponse = z.infer<typeof staffRichMediaUploadResponseSchema>
