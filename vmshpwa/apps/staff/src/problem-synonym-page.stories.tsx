import type { Meta, StoryObj } from '@storybook/react-vite'
import { useState } from 'react'
import { expect, userEvent, within } from 'storybook/test'

import {
  problemSynonymCandidatesResponseSchema,
  problemSynonymImpactResponseSchema,
  type ProblemSynonymProblem,
  type ProblemSynonymImpactResponse,
} from '@vmsh/contracts'

import { ProblemSynonymView } from './problem-synonym-page'

const first: ProblemSynonymProblem = {
  problemId: 'problem.n.41.1',
  courseId: 'course.math',
  courseName: 'Математика 5–7',
  courseLessonId: 'course-lesson.math.41',
  lessonNumber: 41,
  groupId: 'group.beginner',
  groupName: 'Начинающие',
  groupCode: 'н',
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
const second: ProblemSynonymProblem = {
  ...first,
  problemId: 'problem.p.41.2',
  groupId: 'group.continuing',
  groupName: 'Продолжающие',
  groupCode: 'п',
  groupLessonId: 'group-lesson.p.41',
  problemNumber: 2,
  problemType: 2,
  answerType: null,
}
const activeSynonymId = 'problem-synonym.ladders'
const activeFirst: ProblemSynonymProblem = {
  ...first,
  problemId: 'problem.n.41.6',
  problemNumber: 6,
  title: 'Расстановка ладей',
  synonymId: activeSynonymId,
}
const activeSecond: ProblemSynonymProblem = {
  ...second,
  problemId: 'problem.p.41.4',
  problemNumber: 4,
  title: 'Расстановка ладей',
  synonymId: activeSynonymId,
}
const data = problemSynonymCandidatesResponseSchema.parse({
  schemaVersion: 1,
  courseLessonId: first.courseLessonId,
  candidates: [
    {
      normalizedTitle: 'орехи и коробки',
      displayTitle: first.title,
      hasGroupConflict: false,
      problems: [first, second],
    },
  ],
  synonymGroups: [
    {
      synonymId: activeSynonymId,
      displayTitle: 'Расстановка ладей',
      version: 2,
      problems: [activeFirst, activeSecond],
    },
  ],
  requestId: 'story-candidates',
})

function impact(
  mode: 'merge' | 'split',
  problems: (typeof data.candidates)[0]['problems'],
  synonymId: string | null,
) {
  return problemSynonymImpactResponseSchema.parse({
    schemaVersion: 1,
    mode,
    synonym: synonymId === null ? null : { synonymId, status: 'active', version: 2 },
    problems,
    selectedProblemIds: problems.map((problem) => problem.problemId),
    addProblemIds: mode === 'merge' ? problems.map((problem) => problem.problemId) : [],
    removeProblemIds: mode === 'split' ? problems.map((problem) => problem.problemId) : [],
    submissionCount: problems.reduce((total, problem) => total + problem.submissionCount, 0),
    reviewCount: problems.reduce((total, problem) => total + problem.reviewCount, 0),
    previewSha256: 'a'.repeat(64),
    requestId: `story-${mode}`,
  })
}

function SynonymHarness() {
  const [preview, setPreview] = useState<ProblemSynonymImpactResponse>()
  const [status, setStatus] = useState('')
  return (
    <div className="p-5">
      <ProblemSynonymView
        data={data}
        onCancelPreview={() => setPreview(undefined)}
        onConfirm={(review, reason) => {
          setStatus(review.mode === 'merge' ? 'Связь подтверждена' : `Связь снята: ${reason}`)
          setPreview(undefined)
        }}
        onPreviewMerge={() => setPreview(impact('merge', [first, second], null))}
        onPreviewSplit={(synonymId, problemIds) =>
          setPreview(
            impact(
              'split',
              [activeFirst, activeSecond].filter((problem) =>
                problemIds.includes(problem.problemId),
              ),
              synonymId,
            ),
          )
        }
        pending={false}
        {...(preview ? { preview } : {})}
      />
      <p aria-live="polite" className="mt-3 text-small" role="status">
        {status}
      </p>
    </div>
  )
}

const meta = {
  title: 'Pages/Staff/Problem synonyms',
  parameters: { canvasPadding: false, layout: 'fullscreen' },
  globals: { density: 'staff' },
} satisfies Meta
export default meta
type Story = StoryObj<typeof meta>

export const CandidateAndActiveGroup: Story = {
  name: 'Candidate and active group',
  render: () => <SynonymHarness />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await userEvent.click(canvas.getByRole('button', { name: 'Проверить объединение' }))
    await expect(canvas.getByText('Предпросмотр влияния')).toBeInTheDocument()
    await userEvent.click(canvas.getByRole('button', { name: 'Объединить' }))
    await expect(canvas.getByText('Связь подтверждена')).toBeInTheDocument()
  },
}

export const SplitRequiresReason: Story = {
  name: 'Split requires reason',
  render: () => <SynonymHarness />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await userEvent.click(canvas.getAllByRole('button', { name: 'Отделить' })[0]!)
    const confirm = canvas.getByRole('button', { name: 'Разделить' })
    await expect(confirm).toBeDisabled()
    await userEvent.type(canvas.getByLabelText('Причина разделения'), 'Ошибочное совпадение')
    await expect(confirm).toBeEnabled()
  },
}
