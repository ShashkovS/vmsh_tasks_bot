import { describe, expect, it, vi } from 'vitest'

import fixture from '@vmsh/contracts/fixtures/classrooms/published-assignments.v1.json'
import familyRuntimeFixture from '@vmsh/contracts/fixtures/runtime/family.v1.json'
import studentRuntimeFixture from '@vmsh/contracts/fixtures/runtime/student.v1.json'
import { runtimeConfigSchemaForAudience } from '@vmsh/contracts'

import {
  createFamilyClassroomAssignmentClient,
  createStudentClassroomAssignmentClient,
  PublishedClassroomProtocolError,
} from './published-classroom-client'

const studentRuntime = runtimeConfigSchemaForAudience('student').parse(
  studentRuntimeFixture.response,
)
const familyRuntime = runtimeConfigSchemaForAudience('family').parse(familyRuntimeFixture.response)

describe('published classroom assignment client', () => {
  it('loads Student assignments through the Student base path', async () => {
    const fetchImplementation = vi.fn(() => Promise.resolve(Response.json(fixture)))
    const response = await createStudentClassroomAssignmentClient(studentRuntime, {
      fetchImplementation,
    }).list()

    expect(response.items[0]?.classroomName).toBe('202')
    expect(fetchImplementation).toHaveBeenCalledWith(
      '/student/api/v1/classroom-assignments',
      expect.objectContaining({ credentials: 'include', method: 'GET' }),
    )
  })

  it('encodes the child identity in the Family path', async () => {
    const fetchImplementation = vi.fn(() => Promise.resolve(Response.json(fixture)))
    await createFamilyClassroomAssignmentClient(familyRuntime, 'student.one', {
      fetchImplementation,
    }).list()

    expect(fetchImplementation).toHaveBeenCalledWith(
      '/family/api/v1/children/student.one/classroom-assignments',
      expect.any(Object),
    )
  })

  it('refreshes once after an expired access cookie', async () => {
    const fetchImplementation = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(new Response(null, { status: 401 }))
      .mockResolvedValueOnce(Response.json(fixture))
    const refreshSession = vi.fn(() => Promise.resolve())

    await createStudentClassroomAssignmentClient(studentRuntime, {
      fetchImplementation,
      refreshSession,
    }).list()

    expect(refreshSession).toHaveBeenCalledOnce()
    expect(fetchImplementation).toHaveBeenCalledTimes(2)
  })

  it('rejects a response outside the runtime contract', async () => {
    const fetchImplementation = vi.fn(() =>
      Promise.resolve(Response.json({ schemaVersion: 1, items: [] })),
    )
    await expect(
      createStudentClassroomAssignmentClient(studentRuntime, { fetchImplementation }).list(),
    ).rejects.toBeInstanceOf(PublishedClassroomProtocolError)
  })
})
