import { expect, it } from 'vitest'
import fixture from '../fixtures/review/contribution.v1.json'
import { reviewContributionQuerySchema, reviewContributionSchema } from './review-contribution'

it('validates personal totals, calendar and additive response compatibility', () => {
  expect(reviewContributionSchema.parse({ ...fixture, future: true })).toEqual(fixture)
  expect(
    reviewContributionSchema.safeParse({ ...fixture, allTime: { ...fixture.allTime, plus: 2000 } })
      .success,
  ).toBe(false)
  expect(reviewContributionSchema.safeParse({ ...fixture, timezone: 'UTC' }).success).toBe(false)
})

it('keeps the query personal and accepts lesson zero', () => {
  expect(reviewContributionQuerySchema.parse({ course: 'c-1', lesson: 0 })).toEqual({
    course: 'c-1',
    lesson: 0,
  })
  expect(reviewContributionQuerySchema.safeParse({ teacher: 'u-2' }).success).toBe(false)
  expect(reviewContributionQuerySchema.safeParse({ lesson: -1 }).success).toBe(false)
})
