import { describe, expect, it } from 'vitest'

import fixture from '../fixtures/classrooms/catalog.v1.json'
import assignmentFixture from '../fixtures/classrooms/assignment-plan.v1.json'
import layoutFixture from '../fixtures/classrooms/layout.v1.json'
import {
  classroomAssignmentPlanEtag,
  classroomAssignmentPlanResponseSchema,
  classroomEtag,
  classroomLayoutEtag,
  classroomLayoutResponseSchema,
  classroomListQuerySchema,
  classroomListResponseSchema,
  classroomQueryKeys,
  createClassroomRequestSchema,
  replaceClassroomLayoutRequestSchema,
  updateClassroomAssignmentPlanRequestSchema,
} from './classrooms'

describe('classroom catalog contracts', () => {
  it('validates the committed catalog fixture', () => {
    const response = classroomListResponseSchema.parse(fixture)
    expect(response.items.map((room) => room.name)).toEqual(['201', 'Актовый зал'])
    expect(classroomEtag(response.items[0]!)).toBe('"classroom.201:v3"')
  })

  it('keeps server-side trimming possible while rejecting empty names', () => {
    expect(
      createClassroomRequestSchema.parse({ schemaVersion: 1, name: '  Актовый зал  ' }).name,
    ).toBe('  Актовый зал  ')
    expect(() => createClassroomRequestSchema.parse({ schemaVersion: 1, name: '   ' })).toThrow()
  })

  it('defaults list state and isolates query keys by filter and principal', () => {
    expect(classroomListQuerySchema.parse({})).toEqual({ search: '', status: 'active' })
    const admin = { audience: 'staff' as const, accountId: 'admin.one' }
    expect(classroomQueryKeys.list(admin)).not.toEqual(
      classroomQueryKeys.list(admin, { status: 'archived', search: 'зал' }),
    )
    expect(classroomQueryKeys.list(admin)).not.toEqual(
      classroomQueryKeys.list({ audience: 'staff', accountId: 'admin.two' }),
    )
  })

  it('rejects unknown response fields and invalid versions', () => {
    expect(() =>
      classroomListResponseSchema.parse({
        ...fixture,
        items: [{ ...fixture.items[0], version: 0 }],
      }),
    ).toThrow()
    expect(() => classroomListResponseSchema.parse({ ...fixture, unexpected: true })).toThrow()
  })
})

describe('classroom layout contracts', () => {
  it('validates the committed event-scoped layout fixture', () => {
    const response = classroomLayoutResponseSchema.parse(layoutFixture)
    expect(response.layout.groups[0]?.inPersonCount).toBe(84)
    expect(response.layout.rooms[0]?.sourceLayoutPublicId).toBe('layout-40')
    if (response.layout.publicId === null || response.layout.version === null) {
      throw new Error('Fixture must contain a persisted layout')
    }
    expect(
      classroomLayoutEtag({
        ...response.layout,
        publicId: response.layout.publicId,
        version: response.layout.version,
      }),
    ).toBe('"layout-41:v3"')
  })

  it('requires virtual identity only for inherited layouts', () => {
    expect(() =>
      classroomLayoutResponseSchema.parse({
        ...layoutFixture,
        layout: { ...layoutFixture.layout, state: 'inherited' },
      }),
    ).toThrow()
    expect(
      classroomLayoutResponseSchema.parse({
        ...layoutFixture,
        layout: {
          ...layoutFixture.layout,
          state: 'inherited',
          publicId: null,
          version: null,
        },
      }).layout.state,
    ).toBe('inherited')
  })

  it('rejects unknown and oversized room mappings', () => {
    expect(() =>
      replaceClassroomLayoutRequestSchema.parse({
        schemaVersion: 1,
        mappings: [{ classroomPublicId: 'room-201', groupLessonPublicId: 'lesson-41', raw: 1 }],
      }),
    ).toThrow()
    expect(() =>
      replaceClassroomLayoutRequestSchema.parse({
        schemaVersion: 1,
        mappings: Array.from({ length: 501 }, () => ({
          classroomPublicId: 'room-201',
          groupLessonPublicId: 'lesson-41',
        })),
      }),
    ).toThrow()
  })

  it('isolates layout query keys by event and principal', () => {
    const admin = { audience: 'staff' as const, accountId: 'admin.one' }
    expect(classroomQueryKeys.layout(admin, 'event-41')).not.toEqual(
      classroomQueryKeys.layout(admin, 'event-42'),
    )
    expect(classroomQueryKeys.layout(admin, 'event-41')).not.toEqual(
      classroomQueryKeys.layout({ audience: 'staff', accountId: 'admin.two' }, 'event-41'),
    )
  })
})

describe('classroom assignment contracts', () => {
  it('validates the committed assignment-plan fixture', () => {
    const response = classroomAssignmentPlanResponseSchema.parse(assignmentFixture)
    expect(response.assignmentPlan.students[0]?.age).toBe(13.6)
    expect(response.assignmentPlan.students[0]?.strength).toBe(8)
    const plan = response.assignmentPlan.plan
    if (plan === null) throw new Error('Fixture must contain a draft plan')
    expect(classroomAssignmentPlanEtag(plan)).toBe('"classroom-plan.41:v2"')
  })

  it('accepts an event with no generated plan', () => {
    const response = classroomAssignmentPlanResponseSchema.parse({
      ...assignmentFixture,
      assignmentPlan: {
        ...assignmentFixture.assignmentPlan,
        plan: null,
        students: [],
      },
    })
    expect(response.assignmentPlan.plan).toBeNull()
  })

  it('rejects duplicate fields and malformed manual assignments', () => {
    expect(() =>
      updateClassroomAssignmentPlanRequestSchema.parse({
        schemaVersion: 1,
        assignments: [
          {
            enrollmentPublicId: 'enrollment-anna',
            classroomPublicId: 'room-201',
            hidden: true,
          },
        ],
      }),
    ).toThrow()
  })

  it('isolates assignment query keys by event and principal', () => {
    const admin = { audience: 'staff' as const, accountId: 'admin.one' }
    expect(classroomQueryKeys.assignmentPlan(admin, 'event-41')).not.toEqual(
      classroomQueryKeys.assignmentPlan(admin, 'event-42'),
    )
    expect(classroomQueryKeys.assignmentPlan(admin, 'event-41')).not.toEqual(
      classroomQueryKeys.assignmentPlan({ audience: 'staff', accountId: 'admin.two' }, 'event-41'),
    )
  })
})
