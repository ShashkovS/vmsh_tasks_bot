import { i18n } from '@lingui/core'
import { cleanup, fireEvent, screen } from '@testing-library/react'
import { afterEach, expect, it } from 'vitest'

import { auditListResponseSchema } from '@vmsh/contracts'
import { renderWithI18n as render } from '@vmsh/test-utils/i18n'

import { StaffAuditView } from './staff-audit-page'

afterEach(cleanup)

// P7: known audit identifiers are interface labels; actor and serialized audit values are data.
it('localizes known audit actions without translating historical event values', () => {
  i18n.activate('en')
  const event = auditListResponseSchema.parse({
    schemaVersion: 1,
    items: [
      {
        eventId: 'audit.student-account',
        occurredAt: '2026-09-26T10:00:00Z',
        audience: 'staff',
        action: 'student.account_created',
        objectType: 'account',
        objectId: 'account.student-179',
        requestId: 'request-student-account',
        actor: {
          userId: 'user.admin-1',
          accountId: 'account.admin-1',
          displayName: 'Петрова Анна',
        },
        before: null,
        after: { titleCached: 'Новости математики' },
      },
    ],
    nextCursor: null,
    requestId: 'audit-page',
  }).items[0]!

  render(
    <StaffAuditView
      events={[event]}
      nextCursor={null}
      objectType="all"
      onFilter={() => undefined}
      onNextPage={() => undefined}
      query=""
    />,
  )

  expect(screen.getByText('Student sign-in created')).toBeTruthy()
  expect(screen.getByText('Петрова Анна')).toBeTruthy()
  fireEvent.click(screen.getByText('Show changes'))
  expect(screen.getByText('Telegram title')).toBeTruthy()
  expect(screen.getByText('Новости математики')).toBeTruthy()
})
