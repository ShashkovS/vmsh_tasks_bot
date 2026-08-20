import type { Meta, StoryObj } from '@storybook/react-vite'
import { useState } from 'react'
import { expect, userEvent, within } from 'storybook/test'

import { Textarea } from '@vmsh/ui'

import type { AttachmentView } from './attachment'
import { ChatComposer } from './chat-composer'
import { ReactionPicker } from './reaction-picker'
import { reactionsForScope } from './reaction'
import { TaskChat, type ChatMessageView } from './task-chat'
import { TestAnswer } from './test-answer'
import { binaryVerdictScale, findVerdict, writtenReviewVerdict } from './verdict-registry'

/*
 * The task dialogue replaces the old «история проверок» block: a student reads
 * one conversation instead of a composer plus a separate result list. States
 * here are the ones production actually reaches — nothing sent yet, waiting for
 * a check, a human verdict with pages, an AI verdict, and a queued send.
 */
const meta = { title: 'Product/TaskChat', parameters: { layout: 'padded' } } satisfies Meta
export default meta
type Story = StoryObj<typeof meta>

function pagePreview(page: number, accent: string) {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="240" height="320" viewBox="0 0 240 320"><rect width="240" height="320" fill="#f7f4eb"/><path d="M24 56h192M24 92h160M24 128h192M24 164h145M24 235h192M24 271h130" stroke="#8f8b82" stroke-width="5" stroke-linecap="round"/><path d="M45 205c28-38 52-38 72 0s45 38 78-4" fill="none" stroke="${accent}" stroke-width="7"/><text x="205" y="300" text-anchor="end" font-family="sans-serif" font-size="24" fill="#3b3935">${page}</text></svg>`
  return `data:image/svg+xml,${encodeURIComponent(svg)}`
}

function Pages({ count }: { count: number }) {
  return (
    <ol className="flex flex-wrap gap-1.5">
      {Array.from({ length: count }, (_, index) => (
        <li key={index}>
          <img
            alt={`Страница ${index + 1}`}
            className="max-h-32 rounded border border-border bg-surface-sunken"
            src={pagePreview(index + 1, index % 2 === 0 ? '#1b7f75' : '#6d5aa7')}
          />
        </li>
      ))}
    </ol>
  )
}

const askedForCheck: ChatMessageView[] = [
  {
    id: 'own-1',
    author: 'student',
    own: true,
    at: '19:41',
    dateLabel: '20 сентября',
    text: 'Соединил четыре точки, получился наклонный квадрат. Фото ниже.',
    media: <Pages count={2} />,
    delivery: 'sent',
  },
]

export const WaitingForReview: Story = {
  name: 'Ждёт проверки',
  render: () => <TaskChat messages={askedForCheck} />,
}

export const HumanVerdict: Story = {
  name: 'Проверка преподавателя',
  render: () => (
    <TaskChat
      messages={[
        ...askedForCheck,
        {
          id: 'review-1',
          author: 'teacher',
          authorName: 'ВМШ 179 Администратор',
          at: '02:02',
          dateLabel: '21 сентября',
          verdict: writtenReviewVerdict(14),
          text: 'Неплохо! Но не доказано, что других квадратов нет.',
          footer: (
            <ReactionPicker
              legend="Ваша реакция на проверку"
              onSelect={() => undefined}
              options={reactionsForScope('student-written')}
              value={null}
            />
          ),
        },
        {
          id: 'own-2',
          author: 'student',
          own: true,
          at: '09:10',
          dateLabel: '21 сентября',
          text: 'Понял, дописал перебор всех наклонов.',
          delivery: 'sent',
          edited: true,
        },
      ]}
    />
  ),
}

export const AiVerdict: Story = {
  name: 'Проверил ИИ',
  render: () => (
    <TaskChat
      messages={[
        ...askedForCheck,
        {
          id: 'review-ai',
          author: 'ai',
          authorName: 'Проверил ИИ',
          at: '19:44',
          dateLabel: '20 сентября',
          verdict: writtenReviewVerdict(16, 'ai'),
          text: 'Пример верный. Обоснование короткое, но достаточное.',
        },
      ]}
    />
  ),
}

export const BotDialogue: Story = {
  name: 'Тестовая задача: разговор с ботом',
  render: () => (
    <TaskChat
      messages={[
        {
          id: 'a1',
          author: 'student',
          own: true,
          at: '18:02',
          dateLabel: '20 сентября',
          text: '1/4',
          delivery: 'sent',
        },
        {
          id: 'c1',
          author: 'bot',
          authorName: 'Автопроверка',
          at: '18:02',
          dateLabel: '20 сентября',
          verdict: findVerdict(binaryVerdictScale, 'rejected')!,
          text: 'Ответ пока неверный.\nНет, это другое число.',
        },
        {
          id: 'a2',
          author: 'student',
          own: true,
          at: '18:05',
          dateLabel: '20 сентября',
          text: '7/3',
          delivery: 'sent',
        },
        {
          id: 'c2',
          author: 'bot',
          authorName: 'Автопроверка',
          at: '18:05',
          dateLabel: '20 сентября',
          verdict: findVerdict(binaryVerdictScale, 'plus')!,
          text: 'Да, ответ принят.\nДа, всё верно!',
        },
      ]}
    />
  ),
}

export const QueuedAndSystem: Story = {
  name: 'Очередь и системное событие',
  render: () => (
    <TaskChat
      messages={[
        ...askedForCheck,
        {
          id: 'system-1',
          author: 'system',
          text: 'Задача перенесена преподавателем в листок 3.',
          at: '20:00',
        },
        {
          id: 'queued-1',
          author: 'student',
          own: true,
          at: '20:14',
          dateLabel: '20 сентября',
          text: 'Дописал недостающий случай.',
          delivery: 'queued',
        },
      ]}
    />
  ),
}

export const Empty: Story = {
  name: 'Пока пусто',
  render: () => (
    <TaskChat
      emptyLabel="Здесь появится переписка по задаче: ваше решение и ответ проверяющего."
      messages={[]}
    />
  ),
}

const composerPages: AttachmentView[] = [
  { id: 'p1', name: '1.jpg', status: 'ready', previewUrl: pagePreview(1, '#1b7f75') },
  { id: 'p2', name: '2.jpg', status: 'processing', previewUrl: pagePreview(2, '#6d5aa7') },
]

export const WrittenComposer: Story = {
  name: 'Композер письменного решения',
  render: function WrittenComposerStory() {
    const [text, setText] = useState('')
    const [pages, setPages] = useState(composerPages)
    return (
      <ChatComposer
        attachments={pages}
        hint={`Фотографии: ${pages.length} из 10`}
        onAttach={() => undefined}
        onRemoveAttachment={(id) => setPages((current) => current.filter((p) => p.id !== id))}
        onSend={() => setText('')}
        sendDisabled={text.trim() === '' && pages.length === 0}
      >
        <Textarea
          aria-label="Ваше решение"
          className="field-sizing-content max-h-56 min-h-11 py-2"
          onChange={(event) => setText(event.target.value)}
          placeholder="Решение или пояснение. Формулы можно приложить фотографией."
          value={text}
        />
      </ChatComposer>
    )
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    // Photos alone are a complete answer, so sending stays available; it closes
    // only once both the text and every page are gone.
    await expect(canvas.getByRole('button', { name: 'Отправить' })).toBeEnabled()
    await userEvent.click(canvas.getByRole('button', { name: 'Страница 2: удалить' }))
    await userEvent.click(canvas.getByRole('button', { name: 'Страница 1: удалить' }))
    await expect(canvas.getByRole('button', { name: 'Отправить' })).toBeDisabled()
    await userEvent.type(canvas.getByLabelText('Ваше решение'), 'Готово')
    await expect(canvas.getByRole('button', { name: 'Отправить' })).toBeEnabled()
  },
}

export const TestComposer: Story = {
  name: 'Композер тестового ответа',
  render: function TestComposerStory() {
    const [answer, setAnswer] = useState('')
    return (
      <ChatComposer
        onSend={() => undefined}
        sendDisabled={answer.trim() === ''}
        sendLabel="Проверить"
      >
        <TestAnswer label="Ваш ответ" onChange={setAnswer} spec={{ type: 'fraction' }} />
      </ChatComposer>
    )
  },
}
