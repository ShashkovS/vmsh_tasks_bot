import { describe, expect, it } from 'vitest'

import fixture from '../fixtures/progress/course-summary.v1.json'

import { courseProgressResponseSchema } from './progress'

describe('personal course progress contract', () => {
  it('parses a personal course summary without cohort fields', () => {
    const parsed = courseProgressResponseSchema.parse(fixture.response)
    expect(parsed.summary.accepted).toBe(3)
    expect(parsed).not.toHaveProperty('distribution')
    expect(parsed).not.toHaveProperty('position')
  })

  it('rejects counters that do not describe every attempted problem', () => {
    expect(
      courseProgressResponseSchema.safeParse({
        ...fixture.response,
        summary: { ...fixture.response.summary, attempted: 99 },
      }).success,
    ).toBe(false)
  })
})
