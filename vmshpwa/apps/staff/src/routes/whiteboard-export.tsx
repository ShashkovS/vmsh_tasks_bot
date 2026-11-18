import { createFileRoute, lazyRouteComponent } from '@tanstack/react-router'
import { z } from 'zod'
export const Route = createFileRoute('/whiteboard-export')({
  validateSearch: z.object({
    course: z.string().optional(),
    lesson: z.coerce.number().int().optional(),
    group: z.string().optional(),
  }),
  component: lazyRouteComponent(() => import('../whiteboard-export-page'), 'WhiteboardExportPage'),
})
