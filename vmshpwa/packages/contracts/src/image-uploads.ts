import { z } from 'zod'

/** Shared browser-image intent; docs/performance/browser-image-uploads.md. */
export const preparedImageSchema = z
  .object({
    clientId: z.uuid(),
    filename: z.string().min(1).max(512),
    sha256: z.string().regex(/^[0-9a-f]{64}$/),
    byteSize: z
      .number()
      .int()
      .positive()
      .max(20 * 1024 * 1024),
    width: z.number().int().positive().max(1920),
    height: z.number().int().positive().max(1920),
  })
  .strict()
export type PreparedImage = z.infer<typeof preparedImageSchema>
export type ImageUploadPurpose = 'written' | 'support' | 'organizer' | 'rich' | 'lesson-block'

const base = { schemaVersion: z.literal(1), uploadId: z.uuid() }
export const imageUploadGrantSchema = z.discriminatedUnion('transport', [
  z.object({ ...base, transport: z.literal('completed') }),
  z.object({ ...base, transport: z.literal('proxy'), expiresAt: z.iso.datetime() }),
  z.object({
    ...base,
    transport: z.literal('s3'),
    expiresAt: z.iso.datetime(),
    url: z.url().refine((value) => new URL(value).protocol === 'https:'),
    method: z.literal('PUT'),
    headers: z
      .object({
        'Content-Type': z.literal('image/webp'),
        'x-amz-checksum-sha256': z.string().regex(/^[A-Za-z0-9+/]{43}=$/),
      })
      .strict(),
  }),
])
export type ImageUploadGrant = z.infer<typeof imageUploadGrantSchema>
