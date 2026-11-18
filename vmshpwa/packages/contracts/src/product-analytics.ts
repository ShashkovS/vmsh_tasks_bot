import { z } from 'zod'

const analyticsAccountSchema = z.object({
  displayName: z.string(),
  currentAudience: z.enum(['student', 'family', 'staff']).nullable(),
})

export const productAnalyticsSummarySchema = z.object({
  activeUsers: z.number().int().nonnegative(),
  pageViews: z.number().int().nonnegative(),
  actions: z.number().int().nonnegative(),
  popularRoutes: z.array(z.object({ routeId: z.string(), count: z.number().int() })),
  requestId: z.string(),
})
export type ProductAnalyticsSummary = z.infer<typeof productAnalyticsSummarySchema>

export const productAnalyticsEventsSchema = z.object({
  events: z.array(
    z.object({
      eventId: z.number().int(),
      occurred_at: z.string(),
      audience: z.enum(['student', 'family', 'staff']),
      account_public_id: z.string(),
      session_public_id: z.string(),
      event_type: z.string(),
      route_id: z.string(),
      entity_type: z.string().nullable(),
      entity_public_id: z.string().nullable(),
      viewport_width: z.number().int(),
      viewport_height: z.number().int(),
      device_pixel_ratio: z.number(),
      pointer_type: z.string(),
      display_mode: z.string(),
      account: analyticsAccountSchema,
    }),
  ),
  nextBefore: z.number().int().nullable(),
  requestId: z.string(),
})
export type ProductAnalyticsEvents = z.infer<typeof productAnalyticsEventsSchema>
