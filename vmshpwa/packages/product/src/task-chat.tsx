import { Bot, Check, Clock, TriangleAlert } from 'lucide-react'
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

/*
 * Only a live person needs a byline. An automatic checker does not: the side of
 * the bubble already says it is not the reader, and the verdict says the rest.
 * An AI check is the exception — it is always marked, so it can never be read
 * as a live teacher.
 */
const defaultAuthorName: Partial<Record<ChatAuthorKind, string>> = {
  teacher: 'Преподаватель',
  admin: 'Администратор',
  ai: 'Проверил ИИ',
}

const deliveryView: Record<ChatDeliveryState, { icon: typeof Check; label: string }> = {
  queued: { icon: Clock, label: 'В очереди' },
  sending: { icon: Clock, label: 'Отправляется' },
  sent: { icon: Check, label: 'Отправлено' },
  failed: { icon: TriangleAlert, label: 'Не отправлено' },
}

/** Delivery is a mark, not a sentence: the word only reaches assistive tech. */
function DeliveryIcon({ state }: { state: ChatDeliveryState }) {
  const { icon: Icon, label } = deliveryView[state]
  return (
    <span className={state === 'failed' ? 'text-danger' : undefined}>
      <Icon aria-hidden="true" className="inline size-3.5" />
      <span className="sr-only">{label}</span>
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
        <span className="max-w-[90%] rounded-full bg-surface-subtle px-2.5 py-0.5 text-center text-caption text-muted-foreground">
          {message.text}
        </span>
      </li>
    )
  }

  const ai = message.author === 'ai'
  const own = message.own ?? message.author === 'student'
  const name = message.authorName ?? defaultAuthorName[message.author] ?? null
  const verdict = message.verdict ? (
    <VerdictMark className="mr-1 align-[-0.15em]" verdict={message.verdict} />
  ) : null
  // Time rides at the end of the text instead of claiming a line of its own.
  const meta = (
    <span className="ml-1.5 inline-flex items-baseline gap-1 align-baseline text-caption text-muted-foreground">
      {message.edited ? <span>изм.</span> : null}
      {message.at ? <time className="font-num">{message.at}</time> : null}
      {message.delivery ? <DeliveryIcon state={message.delivery} /> : null}
    </span>
  )

  return (
    <li className={cn('flex flex-col', own ? 'items-end' : 'items-start')}>
      <div
        className={cn(
          'max-w-[92%] space-y-1 rounded-lg border px-2.5 py-1.5 sm:max-w-[85%]',
          ai
            ? 'border-dashed border-provenance-ai-border bg-provenance-ai-surface'
            : own
              ? 'border-primary/30 bg-primary/10'
              : 'border-border bg-surface',
        )}
      >
        {own || !name ? null : (
          <p className="flex items-center gap-1 text-caption font-medium text-muted-foreground">
            {ai ? <Bot aria-hidden="true" className="size-3.5 text-provenance-ai" /> : null}
            {name}
          </p>
        )}
        {message.text ? (
          <p className="text-small leading-snug whitespace-pre-line text-foreground">
            {verdict}
            {message.text}
            {meta}
          </p>
        ) : null}
        {message.media}
        {message.text ? null : (
          <p className="flex items-center justify-end">
            {verdict}
            {meta}
          </p>
        )}
      </div>
      {message.actions ? <div className="flex flex-wrap gap-1">{message.actions}</div> : null}
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
    <ol aria-label="Переписка по задаче" className={cn('space-y-1 font-sans', className)}>
      {withDateDividers(messages).map(({ message, divider }) => {
        return (
          <Fragment key={message.id}>
            {divider ? (
              <li className="flex justify-center pt-0.5">
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
