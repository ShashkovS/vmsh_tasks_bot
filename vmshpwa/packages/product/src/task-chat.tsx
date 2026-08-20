import { Bot, Check, Clock, TriangleAlert, UserRound } from 'lucide-react'
import { Fragment, type ReactNode } from 'react'

import { cn } from '@vmsh/ui'

import type { VerdictView } from './types'
import { VerdictMark } from './verdict-mark'

/*
 * Task dialogue. Everything around one task — the student's answers and pages,
 * the checker's verdict, a teacher's comment — reads as one chronological
 * conversation, the way the Telegram bot presented it. Authorship stays
 * explicit: an AI or bot check must never be mistaken for a live teacher.
 * See dev/design-system/04-product-components.md and the Student composers in
 * apps/student (written submissions and test answers).
 */
export type ChatAuthorKind = 'student' | 'teacher' | 'admin' | 'ai' | 'bot' | 'system'
export type ChatDeliveryState = 'queued' | 'sending' | 'sent' | 'failed'

export interface ChatMessageView {
  id: string
  author: ChatAuthorKind
  authorName?: string
  /** Time of day, already formatted for the reader. */
  at?: string
  /** Day the message belongs to; a divider appears whenever it changes. */
  dateLabel?: string
  own?: boolean
  text?: ReactNode
  /** Photos, annotated pages — anything rendered under the text. */
  media?: ReactNode
  verdict?: VerdictView
  delivery?: ChatDeliveryState
  edited?: boolean
  /** Message-scoped controls, e.g. «Изменить». */
  actions?: ReactNode
  /** Content under the bubble that is not part of it, e.g. a reaction picker. */
  footer?: ReactNode
}

const defaultAuthorName: Record<Exclude<ChatAuthorKind, 'system'>, string> = {
  student: 'Вы',
  teacher: 'Преподаватель',
  admin: 'Администратор',
  ai: 'Проверил ИИ',
  bot: 'Бот',
}

const deliveryView: Record<ChatDeliveryState, { icon: typeof Check; label: string }> = {
  queued: { icon: Clock, label: 'В очереди' },
  sending: { icon: Clock, label: 'Отправляется' },
  sent: { icon: Check, label: 'Отправлено' },
  failed: { icon: TriangleAlert, label: 'Не отправлено' },
}

function DeliveryMark({ state }: { state: ChatDeliveryState }) {
  const { icon: Icon, label } = deliveryView[state]
  // `cn` merges Tailwind `text-*` classes and reads the project's font-size
  // tokens as colours, so a size and a colour never share one cn() call.
  const tone = state === 'failed' ? 'text-danger' : 'text-muted-foreground'
  return (
    <span className={`inline-flex items-center gap-1 text-caption ${tone}`}>
      <Icon aria-hidden="true" className="size-3.5" />
      {label}
    </span>
  )
}

/** A day divider belongs to the first message of that day, system notes aside. */
function withDateDividers(
  messages: ChatMessageView[],
): { message: ChatMessageView; divider: string | null }[] {
  const items: { message: ChatMessageView; divider: string | null }[] = []
  let currentDate: string | undefined
  for (const message of messages) {
    const divider = message.dateLabel && message.dateLabel !== currentDate ? message.dateLabel : null
    if (message.dateLabel) currentDate = message.dateLabel
    items.push({ message, divider })
  }
  return items
}

export function ChatMessage({ message }: { message: ChatMessageView }) {
  if (message.author === 'system') {
    return (
      <li className="flex justify-center">
        <div className="max-w-[90%] rounded-full bg-surface-subtle px-3 py-1 text-center text-caption text-muted-foreground">
          {message.text}
        </div>
      </li>
    )
  }

  const ai = message.author === 'ai'
  const own = message.own ?? message.author === 'student'
  const name = message.authorName ?? defaultAuthorName[message.author]

  return (
    <li className={cn('flex flex-col gap-1', own ? 'items-end' : 'items-start')}>
      <div
        className={cn(
          'max-w-[92%] space-y-2 rounded-lg border px-3 py-2 sm:max-w-[85%]',
          ai
            ? 'border-dashed border-provenance-ai-border bg-provenance-ai-surface'
            : own
              ? 'border-primary/30 bg-primary/10'
              : 'border-border bg-surface',
        )}
      >
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
          {message.verdict ? <VerdictMark showLabel verdict={message.verdict} /> : null}
          {own ? null : (
            <span className="inline-flex items-center gap-1 text-label font-medium text-foreground">
              {ai ? (
                <Bot aria-hidden="true" className="size-3.5 text-provenance-ai" />
              ) : message.author === 'bot' ? (
                <Bot aria-hidden="true" className="size-3.5 text-muted-foreground" />
              ) : (
                <UserRound aria-hidden="true" className="size-3.5 text-provenance-human" />
              )}
              {name}
            </span>
          )}
        </div>
        {message.text ? (
          <div className="text-small leading-relaxed whitespace-pre-line text-foreground">
            {message.text}
          </div>
        ) : null}
        {message.media}
        <div className="flex flex-wrap items-center justify-end gap-x-2 gap-y-1">
          {message.edited ? (
            <span className="text-caption text-muted-foreground">изменено</span>
          ) : null}
          {message.at ? (
            <time className="font-num text-caption text-muted-foreground">{message.at}</time>
          ) : null}
          {message.delivery ? <DeliveryMark state={message.delivery} /> : null}
        </div>
      </div>
      {message.actions ? <div className="flex flex-wrap gap-1.5">{message.actions}</div> : null}
      {message.footer ? <div className="w-full">{message.footer}</div> : null}
    </li>
  )
}

export interface TaskChatProps {
  messages: ChatMessageView[]
  /** Shown instead of the list while nothing has been sent yet. */
  emptyLabel?: ReactNode
  className?: string
}

export function TaskChat({ messages, emptyLabel, className }: TaskChatProps) {
  if (messages.length === 0) {
    return emptyLabel ? (
      <p className={`text-small ${cn('text-muted-foreground', className)}`}>{emptyLabel}</p>
    ) : null
  }
  return (
    <ol aria-label="Переписка по задаче" className={cn('space-y-2 font-sans', className)}>
      {withDateDividers(messages).map(({ message, divider }) => {
        return (
          <Fragment key={message.id}>
            {divider ? (
              <li className="flex justify-center pt-1">
                <span className="rounded-full bg-surface-subtle px-2.5 py-0.5 text-caption text-muted-foreground">
                  {divider}
                </span>
              </li>
            ) : null}
            <ChatMessage message={message} />
          </Fragment>
        )
      })}
    </ol>
  )
}
