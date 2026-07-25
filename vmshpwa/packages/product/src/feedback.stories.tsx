import type { Meta, StoryObj } from '@storybook/react-vite'
import { useState } from 'react'
import { expect, userEvent, within } from 'storybook/test'

import { AnnotationOverlay, type AnnotationView } from './annotation-overlay'
import { AttemptTimeline, type TimelineEntry } from './attempt-timeline'
import { FeedbackAttention, FeedbackThread, type ThreadMessageView } from './feedback-thread'
import { reactionsForScope } from './reaction'
import { ReactionPicker } from './reaction-picker'
import { VerdictPanel } from './verdict-panel'
import { findVerdict, fullVerdictScale } from './verdict-registry'

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
