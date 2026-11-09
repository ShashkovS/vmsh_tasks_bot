import { z } from 'zod'

import { richHttpsUrlSchema, richLinkUrlSchema } from './rich-document'
import { isRichFileName, maxRichFileBytes } from './rich-files'

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

/** Shared news/banner/lesson file upload; docs/rich-file-attachments.md. */
export const staffRichFileSchema = z
  .object({
    url: richLinkUrlSchema,
    filename: z.string().refine(isRichFileName),
    mimeType: z.string().min(1).max(255),
    byteSize: z.number().int().positive().max(maxRichFileBytes),
  })
  .strip()
export type StaffRichFile = z.infer<typeof staffRichFileSchema>

export const staffRichFileUploadResponseSchema = z
  .object({
    schemaVersion: z.literal(1),
    file: staffRichFileSchema,
    requestId: z.string().min(1),
  })
  .strip()
