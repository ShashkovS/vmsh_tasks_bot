import { expect, it } from 'vitest'
import { homeRealtimeResources } from './realtime-resources'
import { shouldInvalidateRealtimeQuery } from './realtime'
import fixture from '@vmsh/contracts/fixtures/courses/student-home.v1.json'
import { studentHomeResponseSchema } from '@vmsh/contracts'

it('keeps known Home enrollments scoped to their courses and allowed groups', () => {
  const home = studentHomeResponseSchema.parse(fixture.response)
  const resources = homeRealtimeResources(home.courses)
  const meta = { realtimeResources: resources }
  const enrollment = home.courses[0]!.enrollment
  expect(shouldInvalidateRealtimeQuery(meta, ['courses/unrelated/groups/g/lessons'])).toBe(false)
  expect(
    shouldInvalidateRealtimeQuery(meta, [
      `courses/${enrollment.course.courseId}/groups/unrelated/lessons`,
    ]),
  ).toBe(false)
  expect(
    shouldInvalidateRealtimeQuery(meta, [
      `courses/${enrollment.course.courseId}/groups/${enrollment.allowedGroups[0]!.groupId}/lessons`,
    ]),
  ).toBe(true)
  expect(shouldInvalidateRealtimeQuery(meta, ['live-results', 'courses/unrelated/work'])).toBe(
    false,
  )
  expect(shouldInvalidateRealtimeQuery(meta, ['banners'])).toBe(false)
  expect(
    shouldInvalidateRealtimeQuery({ realtimeResources: homeRealtimeResources([]) }, [
      'courses/unrelated/work',
    ]),
  ).toBe(false)
})
