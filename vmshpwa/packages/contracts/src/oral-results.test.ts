import { describe, expect, it } from 'vitest'

import { recordOralResultRequestSchema, staffOralRosterResponseSchema } from './oral-results'

describe('oral result contracts', () => {
  it('parses the compact Staff roster', () => {
    expect(
      staffOralRosterResponseSchema.parse({
        schemaVersion: 1,
        groupLessonId: 'lesson.41',
        students: [{ studentId: 'student.1', displayName: 'Анна Белова' }],
        problems: [{ problemId: 'problem.1', displayNumber: '1', title: 'Ладьи' }],
        requestId: 'request.1',
      }).students[0]?.displayName,
    ).toBe('Анна Белова')
  })

  it('accepts only oral teacher reactions', () => {
    const base = {
      schemaVersion: 1 as const,
      studentId: 'student.1',
      idempotencyKey: 'oral-round.1',
      marks: [{ problemId: 'problem.1', outcome: 'accepted' as const }],
    }
    expect(recordOralResultRequestSchema.safeParse({ ...base, reactionId: 300 }).success).toBe(true)
    expect(recordOralResultRequestSchema.safeParse({ ...base, reactionId: 100 }).success).toBe(
      false,
    )
  })
})
