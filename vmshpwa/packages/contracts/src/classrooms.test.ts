import { describe, expect, it } from 'vitest'

import fixture from '../fixtures/classrooms/catalog.v1.json'
import assignmentFixture from '../fixtures/classrooms/assignment-plan.v1.json'
import assignmentHistoryFixture from '../fixtures/classrooms/assignment-history.v1.json'
import deliveryBatchFixture from '../fixtures/classrooms/delivery-batch.v1.json'
import deliveryPreviewFixture from '../fixtures/classrooms/delivery-preview.v1.json'
import layoutFixture from '../fixtures/classrooms/layout.v1.json'
import publishedAssignmentsFixture from '../fixtures/classrooms/published-assignments.v1.json'
import {
  classroomAssignmentPlanEtag,
  classroomAssignmentPlanResponseSchema,
  classroomAssignmentHistoryResponseSchema,
  classroomDeliveryBatchResponseSchema,
  classroomDeliveryPreviewResponseSchema,
  classroomEtag,
  inPersonEventEtag,
  inPersonEventListResponseSchema,
  classroomLayoutEtag,
  classroomLayoutResponseSchema,
  classroomListQuerySchema,
  classroomListResponseSchema,
  classroomQueryKeys,
  latestClassroomDeliveryBatchResponseSchema,
  publishedClassroomAssignmentListResponseSchema,
  createClassroomRequestSchema,
  replaceClassroomLayoutRequestSchema,
  retryClassroomDeliveryBatchRequestSchema,
  saveInPersonEventRequestSchema,
  updateClassroomAssignmentPlanRequestSchema,
  createClassroomDeliveryBatchRequestSchema,
} from './classrooms'

const eventGroup = {
  groupLessonPublicId: 'group-lesson-0',
  coursePublicId: 'course-math',
  courseName: 'Математика',
  groupPublicId: 'group-beginner',
  groupName: 'Начинающие',
  shortCode: 'н',
  colorKey: 'beginner',
  lessonNumber: 0,
  inPersonCount: 12,
}

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

describe('in-person event contracts', () => {
  it('accepts lesson zero and gives an event its canonical ETag', () => {
    const event = {
      publicId: 'event-0',
      name: 'Очное знакомство',
      startsAt: '2026-09-06T07:00:00Z',
      endsAt: '2026-09-06T10:00:00Z',
      status: 'scheduled' as const,
      version: 1,
      groupLessons: [eventGroup],
    }
    const parsed = inPersonEventListResponseSchema.parse({
      schemaVersion: 1,
      season: { publicId: 'season-2026', code: '2026-27', title: '2026/27' },
      events: [event],
      candidates: [eventGroup],
      requestId: 'events-list',
    })
    expect(parsed.candidates[0]?.lessonNumber).toBe(0)
    expect(inPersonEventEtag(parsed.events[0]!)).toBe('"event-0:v1"')
  })

  it('rejects duplicate group lessons and a backwards interval', () => {
    const base = {
      schemaVersion: 1,
      name: 'Очное знакомство',
      startsAt: '2026-09-06T07:00:00Z',
      endsAt: '2026-09-06T10:00:00Z',
      status: 'scheduled',
      groupLessonPublicIds: ['group-lesson-0'],
    }
    expect(() =>
      saveInPersonEventRequestSchema.parse({
        ...base,
        groupLessonPublicIds: ['group-lesson-0', 'group-lesson-0'],
      }),
    ).toThrow()
    expect(() =>
      saveInPersonEventRequestSchema.parse({
        ...base,
        endsAt: '2026-09-06T06:59:00Z',
      }),
    ).toThrow()
  })

  it('isolates event catalogs by staff principal', () => {
    expect(classroomQueryKeys.events({ audience: 'staff', accountId: 'admin.one' })).not.toEqual(
      classroomQueryKeys.events({ audience: 'staff', accountId: 'admin.two' }),
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

  it('validates the confirmed assignment-history fixture', () => {
    const response = classroomAssignmentHistoryResponseSchema.parse(assignmentHistoryFixture)
    expect(response.items[0]?.classroomName).toBe('202')
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
    expect(
      updateClassroomAssignmentPlanRequestSchema.parse({
        schemaVersion: 1,
        assignments: [
          {
            enrollmentPublicId: 'enrollment-anna',
            classroomPublicId: 'room-201',
            confirmGroupChange: false,
          },
        ],
      }),
    ).toEqual({
      schemaVersion: 1,
      assignments: [
        {
          enrollmentPublicId: 'enrollment-anna',
          classroomPublicId: 'room-201',
          confirmGroupChange: false,
        },
      ],
    })
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

describe('published classroom assignment contracts', () => {
  it('accepts the Student and Family projection fixture', () => {
    const response = publishedClassroomAssignmentListResponseSchema.parse(
      publishedAssignmentsFixture,
    )
    expect(response.items[0]?.classroomName).toBe('202')
  })

  it('rejects a room on a reassigning state', () => {
    const item = publishedAssignmentsFixture.items[0]!
    expect(() =>
      publishedClassroomAssignmentListResponseSchema.parse({
        ...publishedAssignmentsFixture,
        items: [{ ...item, status: 'reassigning' }],
      }),
    ).toThrow()
  })

  it('scopes query keys by account and selected child', () => {
    const family = { audience: 'family' as const, accountId: 'family.one' }
    expect(classroomQueryKeys.publishedAssignments(family, 'student.one')).not.toEqual(
      classroomQueryKeys.publishedAssignments(family, 'student.two'),
    )
  })
})

describe('classroom delivery contracts', () => {
  it('validates safe preview and immutable batch fixtures', () => {
    const preview = classroomDeliveryPreviewResponseSchema.parse(deliveryPreviewFixture)
    const batch = classroomDeliveryBatchResponseSchema.parse(deliveryBatchFixture)
    const latest = latestClassroomDeliveryBatchResponseSchema.parse({
      ...deliveryBatchFixture,
      batch: deliveryBatchFixture.batch,
    })
    expect(preview.preview.telegramUnavailableCount).toBe(1)
    expect(batch.batch.channelCounts.telegram).toEqual({ queued: 2, suppressed: 1 })
    expect(batch.batch.deliveryReport).toEqual({
      channels: {
        pwa: {
          selected: 3,
          eligible: 3,
          suppressed: 0,
          queued: 0,
          attempted: 3,
          succeeded: 3,
          failed: 0,
        },
        telegram: {
          selected: 3,
          eligible: 2,
          suppressed: 1,
          queued: 2,
          attempted: 0,
          succeeded: 0,
          failed: 0,
        },
      },
      deliveredAny: 3,
      deliveredAll: 0,
      partial: 3,
    })
    expect(latest.batch?.publicId).toBe(batch.batch.publicId)
    expect(
      latestClassroomDeliveryBatchResponseSchema.parse({
        schemaVersion: 1,
        batch: null,
        requestId: 'request-empty',
      }).batch,
    ).toBeNull()
    expect(JSON.stringify({ preview, batch, latest })).not.toContain('chatId')
  })

  it('requires one or two unique delivery channels', () => {
    const valid = {
      schemaVersion: 1,
      channels: ['pwa'] as const,
      expectedPlanVersion: 3,
      previewHash: 'a'.repeat(64),
      idempotencyKey: 'delivery-request-1',
    }
    expect(createClassroomDeliveryBatchRequestSchema.parse(valid).channels).toEqual(['pwa'])
    expect(() =>
      createClassroomDeliveryBatchRequestSchema.parse({
        ...valid,
        channels: ['pwa', 'pwa'],
      }),
    ).toThrow()
    expect(
      retryClassroomDeliveryBatchRequestSchema.parse({
        schemaVersion: 1,
        expectedBatchVersion: 3,
        idempotencyKey: 'delivery-retry-1',
      }).expectedBatchVersion,
    ).toBe(3)
  })
})
