import { expect, it } from 'vitest'
import { reviewConversationResponseSchema } from './review-history'

const event = {
  id: 'discussion:1',
  kind: 'discussion',
  at: '2020-01-01',
  author: 'Ученик',
  authorKind: 'student',
  source: 'telegram',
  text: 'Ответ',
  verdict: null,
  symbol: '',
  revisionId: null,
  reviewId: null,
  internal: false,
  action: null,
  transfer: null,
  checkStatus: null,
  problemNumber: '2п.11а',
}
it('validates review-scoped archive media and rejects internal notes and raw paths', () => {
  for (const url of [
    '/staff/api/v1/review/history/r-1/attachments/sa-1',
    '/staff/api/v1/review/history/r-1/legacy-attachments/123',
    '/solutions/secret/photo.png',
    '/staff/api/v1/student-results/u-1/attachments/sa-1',
    'https://example.com/photo.png',
  ]) {
    const response = {
      schemaVersion: 1,
      requestId: 'test',
      nextCursor: null,
      total: 1,
      events: [
        {
          ...event,
          attachments: [{ id: '1', url, available: true, kind: 'image', annotation: null }],
        },
      ],
    }
    expect(reviewConversationResponseSchema.safeParse(response).success).toBe(
      url.startsWith('/staff/api/v1/review/history/'),
    )
    expect(
      reviewConversationResponseSchema.safeParse({
        ...response,
        events: [{ ...response.events[0], internal: true }],
      }).success,
    ).toBe(false)
  }
})
