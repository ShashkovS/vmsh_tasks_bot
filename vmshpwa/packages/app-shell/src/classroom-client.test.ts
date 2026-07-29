import { describe, expect, it, vi } from 'vitest'

import type { RuntimeConfig } from '@vmsh/contracts'
import assignmentFixture from '@vmsh/contracts/fixtures/classrooms/assignment-plan.v1.json'

import { ClassroomProtocolError, createClassroomClient } from './classroom-client'

const runtime: RuntimeConfig = {
  contractVersion: 1,
  audience: 'staff',
  appBase: '/staff',
  apiBase: '/staff/api/v1',
  websocketPath: '/staff/ws',
  instance: 'classroom-client-test',
  serverTime: '2026-07-29T08:00:00Z',
  requestId: 'runtime-request',
  features: { telegram: false, google: false, nats: false, prototype: false },
}

const classroom = {
  publicId: 'classroom.hall',
  name: 'Актовый зал',
  status: 'active' as const,
  createdAt: '2026-07-29T08:00:00Z',
  updatedAt: '2026-07-29T08:00:00Z',
  version: 1,
}

const layout = {
  event: {
    publicId: 'event-41',
    name: 'Очное занятие',
    startsAt: '2026-10-11T10:00:00Z',
    endsAt: '2026-10-11T13:00:00Z',
    status: 'scheduled' as const,
    version: 1,
  },
  state: 'draft' as const,
  publicId: 'layout-41',
  version: 2,
  groups: [],
  rooms: [],
  conflicts: [],
}

function response(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('classroom client', () => {
  it('lists with normalized query parameters and validates the response', async () => {
    const fetchImplementation = vi.fn(() =>
      Promise.resolve(
        response({ schemaVersion: 1, items: [classroom], requestId: 'list-request' }),
      ),
    )
    const client = createClassroomClient(runtime, { fetchImplementation })

    const result = await client.list({ status: 'all', search: 'Актовый зал' })

    expect(result.items).toEqual([classroom])
    expect(fetchImplementation).toHaveBeenCalledWith(
      '/staff/api/v1/classrooms?status=all&search=%D0%90%D0%BA%D1%82%D0%BE%D0%B2%D1%8B%D0%B9+%D0%B7%D0%B0%D0%BB',
      expect.objectContaining({ method: 'GET', credentials: 'include' }),
    )
  })

  it('sends canonical If-Match for rename and archive', async () => {
    const fetchImplementation = vi.fn(() =>
      Promise.resolve(
        response({
          schemaVersion: 1,
          classroom: { ...classroom, version: 2 },
          requestId: 'mutation',
        }),
      ),
    )
    const client = createClassroomClient(runtime, { fetchImplementation })

    await client.rename(classroom, { schemaVersion: 1, name: 'Большой зал' })
    await client.archive(classroom, { schemaVersion: 1 })

    expect(fetchImplementation).toHaveBeenNthCalledWith(
      1,
      '/staff/api/v1/classrooms/classroom.hall',
      expect.objectContaining({
        method: 'PATCH',
        headers: expect.objectContaining({ 'If-Match': '"classroom.hall:v1"' }),
      }),
    )
    expect(fetchImplementation).toHaveBeenNthCalledWith(
      2,
      '/staff/api/v1/classrooms/classroom.hall/archive',
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({ 'If-Match': '"classroom.hall:v1"' }),
      }),
    )
  })

  it('requires 201 and a valid contract from create', async () => {
    const wrongStatus = createClassroomClient(runtime, {
      fetchImplementation: () =>
        Promise.resolve(response({ schemaVersion: 1, classroom, requestId: 'create-request' })),
    })
    await expect(wrongStatus.create({ schemaVersion: 1, name: '201' })).rejects.toBeInstanceOf(
      ClassroomProtocolError,
    )

    const malformed = createClassroomClient(runtime, {
      fetchImplementation: () => Promise.resolve(response({ classroom }, 201)),
    })
    await expect(malformed.create({ schemaVersion: 1, name: '201' })).rejects.toBeInstanceOf(
      ClassroomProtocolError,
    )
  })

  it('reads and mutates one event layout with the current ETag', async () => {
    const fetchImplementation = vi.fn(() =>
      Promise.resolve(response({ schemaVersion: 1, layout, requestId: 'layout-request' })),
    )
    const client = createClassroomClient(runtime, { fetchImplementation })

    await client.getLayout('event-41')
    await client.materializeLayout('event-41', { schemaVersion: 1 })
    await client.replaceLayout('event-41', layout, {
      schemaVersion: 1,
      mappings: [{ classroomPublicId: 'room-201', groupLessonPublicId: 'group-lesson-41' }],
    })
    await client.confirmLayout('event-41', layout, { schemaVersion: 1 })

    expect(fetchImplementation).toHaveBeenNthCalledWith(
      1,
      '/staff/api/v1/in-person-events/event-41/classroom-layout',
      expect.objectContaining({ method: 'GET' }),
    )
    expect(fetchImplementation).toHaveBeenNthCalledWith(
      2,
      '/staff/api/v1/in-person-events/event-41/classroom-layout/materialize',
      expect.objectContaining({ method: 'POST' }),
    )
    expect(fetchImplementation).toHaveBeenNthCalledWith(
      3,
      '/staff/api/v1/in-person-events/event-41/classroom-layout/layout-41/rooms',
      expect.objectContaining({
        method: 'PUT',
        headers: expect.objectContaining({ 'If-Match': '"layout-41:v2"' }),
      }),
    )
    expect(fetchImplementation).toHaveBeenNthCalledWith(
      4,
      '/staff/api/v1/in-person-events/event-41/classroom-layout/layout-41/confirm',
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({ 'If-Match': '"layout-41:v2"' }),
      }),
    )
  })

  it('reads, recalculates and confirms one classroom assignment plan', async () => {
    const fetchImplementation = vi.fn(() => Promise.resolve(response(assignmentFixture)))
    const client = createClassroomClient(runtime, { fetchImplementation })
    const plan = assignmentFixture.assignmentPlan.plan
    if (plan === null) throw new Error('Fixture must contain a plan')

    await client.getAssignmentPlan('event-41')
    await client.recalculateAssignmentPlan('event-41', null, { schemaVersion: 1 })
    await client.recalculateAssignmentPlan('event-41', plan, { schemaVersion: 1 })
    await client.confirmAssignmentPlan('event-41', plan, { schemaVersion: 1 })

    expect(fetchImplementation).toHaveBeenNthCalledWith(
      1,
      '/staff/api/v1/in-person-events/event-41/classroom-assignment-plan',
      expect.objectContaining({ method: 'GET' }),
    )
    expect(fetchImplementation).toHaveBeenNthCalledWith(
      2,
      '/staff/api/v1/in-person-events/event-41/classroom-assignment-plan/recalculate',
      expect.not.objectContaining({
        headers: expect.objectContaining({ 'If-Match': expect.anything() }),
      }),
    )
    expect(fetchImplementation).toHaveBeenNthCalledWith(
      3,
      '/staff/api/v1/in-person-events/event-41/classroom-assignment-plan/recalculate',
      expect.objectContaining({
        headers: expect.objectContaining({ 'If-Match': '"classroom-plan.41:v2"' }),
      }),
    )
    expect(fetchImplementation).toHaveBeenNthCalledWith(
      4,
      '/staff/api/v1/in-person-events/event-41/classroom-assignment-plan/classroom-plan.41/confirm',
      expect.objectContaining({
        headers: expect.objectContaining({ 'If-Match': '"classroom-plan.41:v2"' }),
      }),
    )
  })
})
