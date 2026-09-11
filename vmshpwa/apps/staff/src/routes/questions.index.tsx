import { createFileRoute } from '@tanstack/react-router'
import { z } from 'zod'
import { OrganizerLink, useAuthenticatedPrincipal } from '@vmsh/app-shell'

import { publicIdSchema, supportThreadKindSchema } from '@vmsh/contracts'

import { StaffSupportInboxPage } from '../staff-support-pages'

const questionsSearchSchema = z.object({
  state: z.enum(['all', 'awaiting_staff', 'awaiting_student']).catch('awaiting_staff'),
  kind: supportThreadKindSchema.optional().catch(undefined),
  course: publicIdSchema.optional().catch(undefined),
  group: publicIdSchema.optional().catch(undefined),
})

export const Route = createFileRoute('/questions/')({
  validateSearch: questionsSearchSchema,
  component: StaffQuestionsRoute,
})

function StaffQuestionsRoute() {
  const search = Route.useSearch()
  const principal = useAuthenticatedPrincipal()
  return (
    <>
      {principal.audience === 'staff' && principal.role === 'admin' ? <OrganizerLink /> : null}
      <StaffSupportInboxPage
        filters={{
          state: search.state,
          ...(search.kind ? { kind: search.kind } : {}),
          ...(search.course ? { courseId: search.course } : {}),
          ...(search.group ? { groupId: search.group } : {}),
        }}
      />
    </>
  )
}
