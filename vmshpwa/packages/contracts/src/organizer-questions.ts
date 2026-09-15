import { z } from 'zod'

/** Account-owned correspondence; docs/organizer-questions.md and migration 0088. */
export const organizerPhotoSchema = z
  .object({
    photoId: z.string().regex(/^oqp-\d+$/),
    url: z
      .string()
      .regex(/^\/(student|family|staff)\/api\/v1\/organizer-questions\/photos\/oqp-\d+$/),
    width: z.number().int().positive(),
    height: z.number().int().positive(),
  })
  .strip()
export const organizerSummarySchema = z
  .object({
    threadId: z.string().regex(/^oq-\d+$/),
    title: z.string(),
    owner: z
      .object({ accountId: z.string(), name: z.string(), audience: z.enum(['student', 'family']) })
      .strip(),
    child: z.object({ studentId: z.string(), name: z.string() }).strip().nullable(),
    state: z.enum(['awaiting_staff', 'answered']),
    latestText: z.string(),
    latestAt: z.iso.datetime({ offset: true }),
    latestEntryId: z.number().int(),
  })
  .strip()
export const organizerEntrySchema = z
  .object({
    entryId: z.string(),
    sequence: z.number().int(),
    text: z.string(),
    createdAt: z.iso.datetime({ offset: true }),
    author: z
      .object({ name: z.string(), audience: z.enum(['student', 'family', 'staff']) })
      .strip(),
    photos: z.array(organizerPhotoSchema),
  })
  .strip()
const envelope = { schemaVersion: z.literal(1), requestId: z.string() }
export const organizerListSchema = z
  .object({
    ...envelope,
    items: z.array(organizerSummarySchema),
    nextCursor: z.string().nullable(),
    unreadCount: z.number().int().nonnegative(),
  })
  .strip()
export const organizerThreadSchema = z
  .object({
    ...envelope,
    thread: organizerSummarySchema,
    entries: z.array(organizerEntrySchema),
    nextCursor: z.string().nullable(),
  })
  .strip()
export const organizerSendSchema = z
  .object({
    text: z.string().max(100000),
    photoIds: z.array(z.string().regex(/^oqp-\d+$/)).max(10),
    childId: z.string().nullable(),
    idempotencyKey: z.string().trim().min(1).max(200),
  })
  .strict()
  .refine(
    (v) => v.text.trim().length > 0 || v.photoIds.length > 0,
    'Введите сообщение или добавьте фотографию',
  )
export const organizerSentSchema = z
  .object({ ...envelope, threadId: z.string().regex(/^oq-\d+$/) })
  .strip()
export const organizerUploadedSchema = z
  .object({ ...envelope, photo: organizerPhotoSchema })
  .strip()
export type OrganizerEntry = z.infer<typeof organizerEntrySchema>
export type OrganizerSummary = z.infer<typeof organizerSummarySchema>
export type OrganizerSend = z.infer<typeof organizerSendSchema>
