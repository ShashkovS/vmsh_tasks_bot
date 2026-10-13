import { createFileRoute } from '@tanstack/react-router'
import { z } from 'zod'

import { auditObjectTypeSchema, publicIdSchema } from '@vmsh/contracts'

import { StaffAuditPage } from '../staff-audit-page'

const searchSchema = z.object({
  objectType: auditObjectTypeSchema.catch('all'),
  q: z.string().trim().max(100).catch(''),
  cursor: publicIdSchema.optional().catch(undefined),
})

export const Route = createFileRoute('/audit')({
  validateSearch: searchSchema,
  component: AuditRoute,
})

function AuditRoute() {
  const search = Route.useSearch()
  const navigate = Route.useNavigate()
  return (
    <StaffAuditPage
      cursor={search.cursor ?? null}
      objectType={search.objectType}
      onFilter={(objectType, q) =>
        void navigate({ search: { objectType, q, cursor: undefined }, replace: true })
      }
      onNextPage={(cursor) => void navigate({ search: { ...search, cursor }, replace: false })}
      query={search.q}
    />
  )
}
