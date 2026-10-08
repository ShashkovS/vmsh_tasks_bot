import { describe, expect, it } from 'vitest'
import { studentResultHistorySchema, studentResultsConditionSchema } from './student-results'

describe('student-results archive boundary (docs/student-results.md)', () => {
  it('keeps unavailable or incompatible old conditions separate from history', () => {
    const envelope = { schemaVersion: 1, requestId: 'archive-test' }
    expect(
      studentResultsConditionSchema.parse({
        ...envelope,
        document: { legacy: 'not a web document' },
      }).document,
    ).toBeNull()
    expect(
      studentResultHistorySchema.parse({ events: [], nextCursor: null, total: 0 }).events,
    ).toEqual([])
  })
  it('refuses media paths outside the admin archive namespace', () => {
    const event = {
      id: 'discussion:1',
      kind: 'discussion',
      at: '2020-01-01',
      author: 'Ученик',
      authorKind: 'student',
      source: 'telegram',
      text: null,
      verdict: null,
      symbol: '',
      revisionId: null,
      reviewId: null,
      internal: false,
      action: null,
      transfer: null,
      checkStatus: null,
    }
    for (const url of [
      '/solutions/old-secret/photo.jpg',
      '/student/api/v1/attachments/sa-1',
      'https://example.com/private',
    ]) {
      expect(
        studentResultHistorySchema.safeParse({
          events: [
            {
              ...event,
              attachments: [{ id: '1', url, kind: 'image', available: true, annotation: null }],
            },
          ],
          nextCursor: null,
          total: 1,
        }).success,
      ).toBe(false)
    }
  })
})
