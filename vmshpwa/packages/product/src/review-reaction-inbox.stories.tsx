import type { Meta, StoryObj } from '@storybook/react-vite'
import { useState } from 'react'
import { expect, userEvent, within } from 'storybook/test'

import type { ReviewReactionId, ReviewReactionInboxItem } from '@vmsh/contracts'

import { ReviewReactionInbox, type ReviewReactionInboxKind } from './review-reaction-inbox'

const meta = {
  title: 'Product/Review reaction inbox',
  component: ReviewReactionInbox,
  parameters: { layout: 'padded' },
} satisfies Meta<typeof ReviewReactionInbox>
export default meta
type Story = StoryObj<typeof meta>

const items: ReviewReactionInboxItem[] = [
  {
    itemId: 'reaction-inbox-student',
    reviewId: 'reaction-review-student',
    kind: 'student',
    reactionId: 2,
    reactionLabel: '🙋 Не могу согласиться с проверкой!',
    reactionVersion: 1,
    updatedAt: '2026-07-29T10:10:00.000Z',
    editableUntil: '2026-07-29T11:00:00.000Z',
    student: { studentId: 'student-anna', displayName: 'Анна Белова' },
    reviewer: { staffId: 'teacher-irina', displayName: 'Ирина Соколова' },
    problem: {
      problemId: 'problem-nuts',
      problemNumber: '41н.6',
      problemTitle: 'Орехи и оценки',
      courseId: 'course-math',
      courseName: 'Математика 5–7',
      groupId: 'group-beginner',
      groupName: 'Начинающие',
      groupShortCode: 'н',
      groupColorKey: 'level-1',
    },
    verdict: 15,
    comment: 'Нужно обосновать последний переход.',
    completedAt: '2026-07-29T10:00:00.000Z',
    isLatestReview: true,
    evidenceEntries: [
      {
        entryId: 'entry-anna',
        entryVersion: 1,
        entryKind: 'submission',
        text: 'Пусть сначала у Пети было x орехов. Тогда после первого шага…',
        submittedAt: '2026-07-29T09:35:00.000Z',
        attachments: [],
      },
    ],
  },
  {
    itemId: 'reaction-inbox-teacher',
    reviewId: 'reaction-review-teacher',
    kind: 'teacher',
    reactionId: 103,
    reactionLabel: '🤖 Решение, вероятно, от нейросети.',
    reactionVersion: 1,
    updatedAt: '2026-07-29T09:45:00.000Z',
    editableUntil: '2026-07-29T10:40:00.000Z',
    student: { studentId: 'student-boris', displayName: 'Борис Ветров' },
    reviewer: { staffId: 'teacher-maria', displayName: 'Мария Полякова' },
    problem: {
      problemId: 'problem-rooks',
      problemNumber: '41п.3',
      problemTitle: 'Расстановка ладей',
      courseId: 'course-math',
      courseName: 'Математика 5–7',
      groupId: 'group-continuing',
      groupName: 'Продолжающие',
      groupShortCode: 'п',
      groupColorKey: 'level-2',
    },
    verdict: 17,
    comment: 'Верное и очень короткое решение.',
    completedAt: '2026-07-29T09:40:00.000Z',
    isLatestReview: true,
    evidenceEntries: [
      {
        entryId: 'entry-boris',
        entryVersion: 1,
        entryKind: 'submission',
        text: 'Расставим ладьи по одной в каждой строке и каждом столбце.',
        submittedAt: '2026-07-29T09:25:00.000Z',
        attachments: [],
      },
    ],
  },
]

function InboxHarness() {
  const [kind, setKind] = useState<ReviewReactionInboxKind>('all')
  const [reactionId, setReactionId] = useState<ReviewReactionId | null>(null)
  const [recheckingReviewId, setRecheckingReviewId] = useState<string | null>(null)
  return (
    <div className="space-y-3">
      <ReviewReactionInbox
        items={items.filter(
          (item) =>
            (kind === 'all' || item.kind === kind) &&
            (reactionId === null || item.reactionId === reactionId),
        )}
        kind={kind}
        onKindChange={(nextKind) => {
          setKind(nextKind)
          setReactionId(null)
        }}
        onReactionIdChange={setReactionId}
        onRecheck={(item) => setRecheckingReviewId(item.reviewId)}
        reactionId={reactionId}
        recheckingReviewId={recheckingReviewId}
      />
      {recheckingReviewId ? <p role="status">Открыта перепроверка: {recheckingReviewId}</p> : null}
    </div>
  )
}

export const CurrentWrittenReactions: Story = {
  name: 'Текущие письменные реакции',
  args: { items, kind: 'all', onKindChange: () => undefined },
  render: () => <InboxHarness />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await expect(canvas.getByText('Анна Белова')).toBeVisible()
    await expect(canvas.getByText('Борис Ветров')).toBeVisible()
    await userEvent.click(canvas.getByRole('button', { name: 'От учеников' }))
    await expect(canvas.getByText('Анна Белова')).toBeVisible()
    await expect(canvas.queryByText('Борис Ветров')).toBeNull()
    await userEvent.click(canvas.getByRole('button', { name: /Не могу согласиться с проверкой/ }))
    await expect(canvas.getByText('Анна Белова')).toBeVisible()
    await userEvent.click(canvas.getByRole('button', { name: 'Перепроверить результат' }))
    await expect(canvas.getByText('Открыта перепроверка: reaction-review-student')).toBeVisible()
  },
}

export const AlreadyRechecked: Story = {
  name: 'Реакция на прежнюю проверку',
  args: {
    items: [{ ...items[0]!, isLatestReview: false }],
    kind: 'all',
    onKindChange: () => undefined,
    onRecheck: () => undefined,
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await expect(canvas.getByText('Уже есть более новая проверка')).toBeVisible()
    await expect(canvas.queryByRole('button', { name: 'Перепроверить результат' })).toBeNull()
  },
}

export const Empty: Story = {
  name: 'Нет активных реакций',
  args: { items: [], kind: 'all', onKindChange: () => undefined },
}
