import runtimeFixture from '@vmsh/contracts/fixtures/runtime/staff.v1.json'
import { runtimeConfigSchemaForAudience } from '@vmsh/contracts'
import { describe, expect, it, vi } from 'vitest'

import { createProblemSynonymClient } from './problem-synonym-client'

const runtime = runtimeConfigSchemaForAudience('staff').parse(runtimeFixture.response)
const problem = {
  problemId: 'problem.n.41.1',
  courseId: 'course.math',
  courseName: 'Математика 5–7',
  courseLessonId: 'course-lesson.math.41',
  lessonNumber: 41,
  groupId: 'group.beginner',
  groupName: 'Начинающие',
  groupCode: 'n',
  groupLessonId: 'group-lesson.n.41',
  problemNumber: 1,
  problemItem: '',
  title: 'Орехи и коробки',
  problemType: 1,
  answerType: 2,
  submissionCount: 3,
  reviewCount: 1,
  synonymId: null,
}
const otherProblem = {
  ...problem,
  problemId: 'problem.p.41.2',
  groupId: 'group.continuing',
  groupName: 'Продолжающие',
  groupCode: 'p',
  groupLessonId: 'group-lesson.p.41',
}
const preview = {
  schemaVersion: 1,
  mode: 'merge',
  synonym: null,
  problems: [problem, otherProblem],
  selectedProblemIds: [problem.problemId, otherProblem.problemId],
  addProblemIds: [problem.problemId, otherProblem.problemId],
  removeProblemIds: [],
  submissionCount: 6,
  reviewCount: 2,
  previewSha256: 'a'.repeat(64),
  requestId: 'preview-one',
} as const

describe('problem synonym client', () => {
  it('loads the selected course lesson through the Staff boundary', async () => {
    const fetchImplementation = vi.fn<typeof fetch>().mockResolvedValue(
      Response.json({
        schemaVersion: 1,
        courseLessonId: problem.courseLessonId,
        candidates: [
          {
            normalizedTitle: 'орехи и коробки',
            displayTitle: problem.title,
            hasGroupConflict: false,
            problems: [problem, otherProblem],
          },
        ],
        synonymGroups: [],
        requestId: 'candidates-one',
      }),
    )
    const response = await createProblemSynonymClient(runtime, { fetchImplementation }).candidates(
      problem.courseLessonId,
    )
    expect(response.candidates).toHaveLength(1)
    expect(fetchImplementation.mock.calls[0]?.[0]).toBe(
      `/staff/api/v1/course-lessons/${problem.courseLessonId}/synonym-candidates`,
    )
  })

  it('previews and applies the exact reviewed merge', async () => {
    const applied = {
      ...preview,
      result: {
        synonymId: 'problem-synonym.one',
        status: 'active',
        version: 1,
        changed: true,
      },
      requestId: 'merge-one',
    }
    const fetchImplementation = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(Response.json(preview))
      .mockResolvedValueOnce(Response.json(applied))
    const client = createProblemSynonymClient(runtime, { fetchImplementation })
    const reviewed = await client.preview({
      schemaVersion: 1,
      mode: 'merge',
      problemIds: [problem.problemId, otherProblem.problemId],
      synonymId: null,
    })
    await client.merge({
      schemaVersion: 1,
      problemIds: reviewed.selectedProblemIds,
      previewSha256: reviewed.previewSha256,
    })
    expect(fetchImplementation.mock.calls[0]?.[0]).toBe(
      '/staff/api/v1/problem-synonyms/impact-preview',
    )
    expect(fetchImplementation.mock.calls[1]?.[0]).toBe('/staff/api/v1/problem-synonyms/merge')
  })

  it('retries once after refreshing an expired session', async () => {
    const refreshSession = vi.fn().mockResolvedValue(undefined)
    const fetchImplementation = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(
        Response.json(
          { error: { code: 'unauthorized', message: 'Войдите', requestId: 'expired' } },
          { status: 401 },
        ),
      )
      .mockResolvedValueOnce(Response.json(preview))
    await createProblemSynonymClient(runtime, { fetchImplementation, refreshSession }).preview({
      schemaVersion: 1,
      mode: 'merge',
      problemIds: [problem.problemId, otherProblem.problemId],
      synonymId: null,
    })
    expect(refreshSession).toHaveBeenCalledOnce()
    expect(fetchImplementation).toHaveBeenCalledTimes(2)
  })

  it('rejects additive response fields', async () => {
    const fetchImplementation = vi
      .fn<typeof fetch>()
      .mockResolvedValue(Response.json({ ...preview, hiddenRewrite: true }))
    await expect(
      createProblemSynonymClient(runtime, { fetchImplementation }).preview({
        schemaVersion: 1,
        mode: 'merge',
        problemIds: [problem.problemId, otherProblem.problemId],
        synonymId: null,
      }),
    ).rejects.toThrow()
  })
})
