import { describe, expect, it } from 'vitest'

import studentAuth from '../fixtures/auth/student.v1.json'
import familyAuth from '../fixtures/auth/family.v1.json'
import staffAuth from '../fixtures/auth/staff.v1.json'
import content from '../fixtures/content/web-document.v1.json'
import access from '../fixtures/courses/student-access.v1.json'
import home from '../fixtures/courses/student-home.v1.json'
import lessons from '../fixtures/courses/student-lessons.v1.json'
import problems from '../fixtures/courses/student-problems.v1.json'
import written from '../fixtures/submissions/written-thread.v1.json'
import { authContextSchema, studentLoginRequestSchema } from './auth'
import { webContentDocumentSchema } from './content'
import {
  studentCourseAccessResponseSchema,
  studentHomeResponseSchema,
  studentLessonListResponseSchema,
  studentProblemListResponseSchema,
} from './courses'
import { reviewSeriesConditionSchema, reviewSeriesHistorySchema } from './review-series'
import { writtenThreadResponseSchema } from './written-submissions'

// docs/api-response-compatibility.md: additions must work at every object depth,
// including recursive document nodes and objects inside response arrays.
function withFutureFields(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(withFutureFields)
  if (value === null || typeof value !== 'object') return value
  return {
    ...Object.fromEntries(
      Object.entries(value).map(([key, child]) => [key, withFutureFields(child)]),
    ),
    futureMetadata: { version: 2 },
  }
}

describe('additive API response compatibility', () => {
  it.each([
    ['student auth', authContextSchema, studentAuth.authContext],
    ['family auth', authContextSchema, familyAuth.authContext],
    ['staff auth', authContextSchema, staffAuth.authContext],
    ['course access', studentCourseAccessResponseSchema, access.response],
    ['home', studentHomeResponseSchema, home.response],
    ['lessons', studentLessonListResponseSchema, lessons.response],
    ['problems', studentProblemListResponseSchema, problems.response],
    ['written thread', writtenThreadResponseSchema, written.threadResponse],
    ['recursive content', webContentDocumentSchema, content.document],
    [
      'series condition',
      reviewSeriesConditionSchema,
      { schemaVersion: 1, label: '1п.10', document: content.document },
    ],
    [
      'series history',
      reviewSeriesHistorySchema,
      {
        schemaVersion: 1,
        items: [{ reviewId: 'r-683', materialKey: 'se-1' }],
        nextCursor: 'r-682',
      },
    ],
  ] as const)('%s ignores additions without changing known data', (_name, schema, payload) => {
    expect(schema.parse(withFutureFields(payload))).toEqual(schema.parse(payload))
  })

  it('still rejects missing fields, incorrect types, versions and unknown node kinds', () => {
    const valid = { schemaVersion: 1, label: '1п.10', document: content.document }
    for (const invalid of [
      { ...valid, schemaVersion: 2 },
      { ...valid, label: 10 },
      { schemaVersion: 1, document: null },
      { ...valid, document: { ...content.document, introduction: [{ type: 'future-block' }] } },
    ]) {
      expect(reviewSeriesConditionSchema.safeParse(withFutureFields(invalid)).success).toBe(false)
    }
  })

  it('keeps client-controlled login requests strict', () => {
    expect(
      studentLoginRequestSchema.safeParse({ ...studentAuth.loginRequest, accountId: 'other' })
        .success,
    ).toBe(false)
  })
})
