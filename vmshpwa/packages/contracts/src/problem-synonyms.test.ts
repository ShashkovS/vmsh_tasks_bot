import { describe, expect, it } from 'vitest'

import {
  problemSynonymCandidatesResponseSchema,
  problemSynonymImpactRequestSchema,
  problemSynonymImpactResponseSchema,
  problemSynonymQueryKeys,
} from './problem-synonyms'

const firstProblem = {
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

const secondProblem = {
  ...firstProblem,
  problemId: 'problem.p.41.2',
  groupId: 'group.continuing',
  groupName: 'Продолжающие',
  groupCode: 'p',
  groupLessonId: 'group-lesson.p.41',
  problemNumber: 2,
  problemType: 3,
  answerType: null,
}

describe('problem synonym contracts', () => {
  it('accepts candidates with different submission and answer types', () => {
    const response = problemSynonymCandidatesResponseSchema.parse({
      schemaVersion: 1,
      courseLessonId: firstProblem.courseLessonId,
      candidates: [
        {
          normalizedTitle: 'орехи и коробки',
          displayTitle: firstProblem.title,
          hasGroupConflict: false,
          problems: [firstProblem, secondProblem],
        },
      ],
      synonymGroups: [],
      requestId: 'synonym-candidates-one',
    })
    expect(response.candidates[0]?.problems).toHaveLength(2)
  })

  it('rejects duplicate IDs and an incomplete split request', () => {
    expect(() =>
      problemSynonymImpactRequestSchema.parse({
        schemaVersion: 1,
        mode: 'merge',
        problemIds: [firstProblem.problemId, firstProblem.problemId],
        synonymId: null,
      }),
    ).toThrow()
    expect(() =>
      problemSynonymImpactRequestSchema.parse({
        schemaVersion: 1,
        mode: 'split',
        problemIds: [firstProblem.problemId],
        synonymId: null,
      }),
    ).toThrow()
  })

  it('accepts an applied response without changing concrete records', () => {
    const response = problemSynonymImpactResponseSchema.parse({
      schemaVersion: 1,
      mode: 'merge',
      synonym: null,
      problems: [firstProblem, secondProblem],
      selectedProblemIds: [firstProblem.problemId, secondProblem.problemId],
      addProblemIds: [firstProblem.problemId, secondProblem.problemId],
      removeProblemIds: [],
      submissionCount: 6,
      reviewCount: 2,
      previewSha256: 'a'.repeat(64),
      result: {
        synonymId: 'problem-synonym.one',
        status: 'active',
        version: 1,
        changed: true,
      },
      requestId: 'merge-one',
    })
    expect(response.result?.changed).toBe(true)
  })

  it('scopes lesson queries by authenticated principal', () => {
    const first = problemSynonymQueryKeys.lesson(
      { audience: 'staff', accountId: 'admin.one' },
      firstProblem.courseLessonId,
    )
    const second = problemSynonymQueryKeys.lesson(
      { audience: 'staff', accountId: 'admin.two' },
      firstProblem.courseLessonId,
    )
    expect(first).not.toEqual(second)
  })
})
