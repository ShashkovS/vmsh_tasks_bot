import type { Meta, StoryObj } from '@storybook/react-vite'
import { useState } from 'react'
import { expect, userEvent, within } from 'storybook/test'

import type { WrittenStudentReaction } from '@vmsh/contracts'

import { AnnotationOverlay, type AnnotationView } from './annotation-overlay'
import { AttemptTimeline, type TimelineEntry } from './attempt-timeline'
import { FeedbackAttention, FeedbackThread, type ThreadMessageView } from './feedback-thread'
import { reactionsForScope } from './reaction'
import { ReactionPicker } from './reaction-picker'
import { SupportComposer } from './support-dialogue'
import { VerdictPanel } from './verdict-panel'
import { findVerdict, fullVerdictScale } from './verdict-registry'
import { WrittenReviewHistory } from './written-review-history'

const meta = { title: 'Product/Feedback', parameters: { layout: 'padded' } } satisfies Meta
export default meta
type Story = StoryObj<typeof meta>

const partial = findVerdict(fullVerdictScale, 'plus-minus')!
const aiVerdict = { ...findVerdict(fullVerdictScale, 'minus-plus')!, provenance: 'ai' as const }

const timeline: TimelineEntry[] = [
  { id: 'v', at: '26 января, 12:30', label: 'Проверено', verdict: partial },
  { id: 's', at: '25 января, 21:04', label: 'Решение отправлено' },
  { id: 'd', at: '24 января, 20:12', label: 'Дослали фото', detail: 'Добавлена страница 2' },
]

const messages: ThreadMessageView[] = [
  {
    id: 'm1',
    author: { kind: 'teacher', name: 'И. Соколов' },
    at: '12:30',
    channel: 'pwa',
    body: 'Хорошо, но проверь отдельно случай k = 1.',
  },
  {
    id: 'm2',
    author: { kind: 'student' },
    at: '12:40',
    channel: 'telegram',
    body: 'Спасибо, поправил!',
    own: true,
  },
]

function ResultHarness() {
  const [reaction, setReaction] = useState<number | null>(null)
  return (
    <div className="max-w-xl space-y-5">
      <section className="space-y-2">
        <h2 className="text-label font-medium text-foreground">Результат</h2>
        <VerdictPanel
          at="26 января, 12:30"
          author="И. Соколов"
          comment="Идея верная. Не хватает разбора случая k = 1 — допиши и присылай."
          verdict={partial}
        />
      </section>

      <section className="space-y-2">
        <div className="flex items-center gap-2">
          <h2 className="text-label font-medium text-foreground">Обсуждение</h2>
          <FeedbackAttention />
        </div>
        <FeedbackThread messages={messages} />
      </section>

      <section className="space-y-2">
        <h2 className="text-label font-medium text-foreground">История</h2>
        <AttemptTimeline entries={timeline} />
      </section>

      <ReactionPicker
        legend="Ваша реакция на проверку"
        onSelect={setReaction}
        options={reactionsForScope('student-written')}
        value={reaction}
      />
    </div>
  )
}

export const Result: Story = {
  name: 'Результат, обсуждение, реакция',
  render: () => <ResultHarness />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)

    // История сворачивается; последний вердикт виден сразу.
    await expect(canvas.queryByText('Дослали фото')).not.toBeInTheDocument()
    await userEvent.click(canvas.getByRole('button', { name: /Показать историю/ }))
    await expect(canvas.getByText('Дослали фото')).toBeInTheDocument()

    // Реакция ученика выбирается и снимается.
    const ok = canvas.getByRole('button', { name: 'Ок. Всё ясно.' })
    await expect(ok).toHaveAttribute('aria-pressed', 'false')
    await userEvent.click(ok)
    await expect(ok).toHaveAttribute('aria-pressed', 'true')
  },
}

export const AiResult: Story = {
  name: 'Проверка ИИ (визуально отделена)',
  render: () => (
    <div className="max-w-xl">
      <VerdictPanel
        at="26 января, 12:31"
        comment="Похоже, разобран только случай k = n. Стоит рассмотреть общий k."
        verdict={aiVerdict}
      />
    </div>
  ),
}

export const TeacherReaction: Story = {
  name: 'Внутренняя реакция учителя',
  render: () => (
    <div className="max-w-xl">
      <ReactionPicker
        compact
        legend="Внутренняя пометка (не видна ученику)"
        onSelect={() => undefined}
        options={reactionsForScope('teacher-written')}
        value={100}
      />
    </div>
  ),
}

function PrivateSupportDialogueHarness() {
  const [value, setValue] = useState('')
  const [sent, setSent] = useState('')
  return (
    <div className="max-w-xl space-y-4">
      <FeedbackThread
        messages={[
          {
            id: 'support-student',
            author: { kind: 'student', name: 'Анна Белова' },
            at: '12:08',
            channel: 'pwa',
            body: 'Не понимаю переход после второй формулы.',
            own: true,
          },
          {
            id: 'support-teacher',
            author: { kind: 'teacher', name: 'И. Соколов' },
            at: '12:15',
            channel: 'staff',
            body: 'Посмотрите на остатки по модулю 7 — там используется только их равенство.',
          },
          {
            id: 'support-system',
            author: { kind: 'system' },
            at: '12:15',
            channel: 'system',
            body: 'Ответ преподавателя доставлен.',
          },
        ]}
      />
      <SupportComposer
        onSubmit={() => setSent(value)}
        onValueChange={setValue}
        saveState={value ? 'saved' : 'idle'}
        value={value}
      />
      <output className="sr-only" data-testid="support-sent">
        {sent}
      </output>
    </div>
  )
}

export const PrivateSupportDialogue: Story = {
  name: 'Приватный вопрос и сохранённый ответ',
  render: () => <PrivateSupportDialogueHarness />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await expect(canvas.getByText('в кабинете преподавателя')).toBeVisible()
    await expect(canvas.getByText('системное событие')).toBeVisible()
    const message = canvas.getByLabelText('Сообщение')
    await userEvent.type(message, 'Теперь понятно, спасибо!')
    await expect(canvas.getByText('Черновик сохранён на этом устройстве.')).toBeVisible()
    await userEvent.click(canvas.getByRole('button', { name: 'Отправить' }))
    await expect(canvas.getByTestId('support-sent')).toHaveTextContent('Теперь понятно, спасибо!')
  },
}

const annotations: AnnotationView[] = [
  { id: 'a1', kind: 'highlight', x: 0.08, y: 0.34, w: 0.5, h: 0.08 },
  { id: 'a2', kind: 'pen', x: 0.72, y: 0.3 },
  {
    id: 'a3',
    kind: 'comment',
    x: 0.6,
    y: 0.52,
    author: 'И. Соколов',
    note: 'Здесь пропущен случай k = 1 — из-за этого ответ неполный.',
  },
]

export const Annotations: Story = {
  name: 'Аннотации на работе',
  render: () => (
    <div className="max-w-md">
      <AnnotationOverlay annotations={annotations}>
        <div className="aspect-[4/3] space-y-2 p-4 font-reading text-small text-foreground">
          <p>Пусть на доске n×n стоят ладьи, не бьющие друг друга.</p>
          <p>Тогда в каждой строке и каждом столбце не более одной ладьи.</p>
          <p>Значит, число расстановок равно n! для k = n.</p>
        </div>
      </AnnotationOverlay>
    </div>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await expect(canvas.queryByText(/пропущен случай/)).not.toBeInTheDocument()
    await userEvent.click(canvas.getByRole('button', { name: 'Комментарий 1' }))
    await expect(canvas.getByText(/пропущен случай/)).toBeInTheDocument()
  },
}

const reviewedPhoto =
  'data:image/svg+xml;charset=utf-8,' +
  encodeURIComponent(
    '<svg xmlns="http://www.w3.org/2000/svg" width="640" height="420" viewBox="0 0 640 420"><rect width="640" height="420" fill="white"/><path d="M70 90h500M70 150h430M70 210h470M70 270h390" stroke="#94a3b8" stroke-width="5"/><text x="70" y="350" font-family="serif" font-size="30">x + 7 = 19, поэтому x = 12</text></svg>',
  )

export const ReviewedWrittenPhoto: Story = {
  name: 'Проверенная письменная работа',
  render: () => (
    <div className="max-w-xl">
      <WrittenReviewHistory
        entries={[
          {
            attachments: [{ attachmentId: 'reviewed-page-one', mediaPath: reviewedPhoto }],
          },
        ]}
        reviews={[
          {
            reviewId: 'reviewed-result-one',
            targetProblemId: 'problem-41-n-6',
            verdict: 15,
            commentEntryId: 'reviewed-comment-one',
            comment: 'Идея верная. Допишите обоснование выделенного перехода.',
            reviewerName: 'И. Соколов',
            source: 'staff',
            evidenceEntryIds: ['reviewed-entry-one'],
            annotations: [
              {
                attachmentId: 'reviewed-page-one',
                schemaVersion: 1,
                rotation: 0,
                marks: [
                  {
                    markId: 'reviewed-mark-one',
                    kind: 'rectangle',
                    data: {
                      x: 0.08,
                      y: 0.68,
                      width: 0.78,
                      height: 0.17,
                      strokeWidth: 0.008,
                      color: 'red',
                    },
                  },
                ],
              },
            ],
            studentReaction: null,
            completedAt: '2026-01-26T09:30:00.000Z',
          },
        ]}
      />
    </div>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await expect(canvas.getByRole('region', { name: 'Последняя проверка' })).toBeVisible()
    await expect(canvas.getByText(/Допишите обоснование/)).toBeVisible()
    await expect(canvas.getByAltText('Проверенная страница решения 1')).toBeVisible()
    await expect(canvas.queryByText(/внутренняя пометка/i)).not.toBeInTheDocument()
  },
}

function ReviewedStudentReactionHarness() {
  const [studentReaction, setStudentReaction] = useState<WrittenStudentReaction | null>(null)
  return (
    <div className="max-w-xl">
      <WrittenReviewHistory
        entries={[]}
        onStudentReactionChange={(_reviewId, reactionId, expectedVersion) => {
          setStudentReaction({
            reactionId,
            version: expectedVersion + 1,
            editableUntil: '2026-01-26T10:30:00.000Z',
            updatedAt: '2026-01-26T09:45:00.000Z',
            deleted: reactionId === null,
          })
        }}
        reactionNow="2026-01-26T09:40:00.000Z"
        reviews={[
          {
            reviewId: 'reviewed-reaction-one',
            targetProblemId: 'problem-41-n-6',
            verdict: 16,
            commentEntryId: 'reviewed-reaction-comment',
            comment: 'Теперь всё обосновано аккуратно.',
            reviewerName: 'И. Соколов',
            source: 'staff',
            evidenceEntryIds: ['reviewed-reaction-entry'],
            annotations: [],
            studentReaction,
            completedAt: '2026-01-26T09:30:00.000Z',
          },
        ]}
      />
    </div>
  )
}

export const ReviewedStudentReaction: Story = {
  name: 'Реакция ученика на конкретную проверку',
  render: () => <ReviewedStudentReactionHarness />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    const disagreement = canvas.getByRole('button', {
      name: 'Не могу согласиться с проверкой!',
    })
    await userEvent.click(disagreement)
    await expect(disagreement).toHaveAttribute('aria-pressed', 'true')
    await userEvent.click(disagreement)
    await expect(disagreement).toHaveAttribute('aria-pressed', 'false')
  },
}

export const FamilyStudentReaction: Story = {
  name: 'Реакция ребёнка для семьи',
  render: () => (
    <div className="max-w-xl">
      <WrittenReviewHistory
        entries={[]}
        reactionNow="2026-01-26T09:40:00.000Z"
        reviews={[
          {
            reviewId: 'family-reviewed-reaction-one',
            targetProblemId: 'problem-41-n-6',
            verdict: 15,
            commentEntryId: 'family-reviewed-reaction-comment',
            comment: 'Нужно дописать последний переход.',
            reviewerName: 'И. Соколов',
            source: 'staff',
            evidenceEntryIds: ['family-reviewed-reaction-entry'],
            annotations: [],
            studentReaction: {
              reactionId: 1,
              version: 1,
              editableUntil: '2026-01-26T10:30:00.000Z',
              updatedAt: '2026-01-26T09:35:00.000Z',
              deleted: false,
            },
            completedAt: '2026-01-26T09:30:00.000Z',
          },
        ]}
      />
    </div>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await expect(canvas.getByText('Реакция ученика')).toBeVisible()
    await expect(canvas.getByText('Непонятно, что не так…')).toBeVisible()
    await expect(canvas.queryByRole('button', { name: 'Непонятно, что не так…' })).toBeNull()
  },
}
