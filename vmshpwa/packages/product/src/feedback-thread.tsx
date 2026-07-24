import { Bot, Send, Smartphone } from 'lucide-react'
import type { ReactNode } from 'react'

import { cn } from '@vmsh/ui'

/*
 * Feedback thread linking pointwise annotations and text messages. Each message
 * shows author, time and channel; AI feedback is a distinct author and can
 * never be confused with a live teacher. Asymmetric visibility is a permission
 * concern — a Student/Family view-model simply never contains hidden messages.
 */
export type ThreadAuthorKind = 'student' | 'teacher' | 'admin' | 'ai'

export interface ThreadMessageView {
  id: string
  author: { kind: ThreadAuthorKind; name?: string }
  at: string
  channel?: 'pwa' | 'telegram'
  body: ReactNode
  /** True for the viewer's own message (aligned to the trailing edge). */
  own?: boolean
}

const authorName: Record<ThreadAuthorKind, string> = {
  student: 'Ученик',
  teacher: 'Преподаватель',
  admin: 'Администратор',
  ai: 'ИИ',
}

function ChannelBadge({ channel }: { channel: 'pwa' | 'telegram' }) {
  const Icon = channel === 'telegram' ? Send : Smartphone
  const label = channel === 'telegram' ? 'через Telegram' : 'в приложении'
  return (
    <span className="inline-flex items-center gap-1 text-caption text-muted-foreground">
      <Icon aria-hidden="true" className="size-3.5" />
      {label}
    </span>
  )
}

export function ThreadMessage({ message }: { message: ThreadMessageView }) {
  const ai = message.author.kind === 'ai'
  const name = message.author.name ?? authorName[message.author.kind]
  return (
    <li className={cn('flex', message.own && 'justify-end')}>
      <div
        className={cn(
          'max-w-[85%] space-y-1 rounded-lg border px-3 py-2',
          ai
            ? 'border-dashed border-provenance-ai-border bg-provenance-ai-surface'
            : message.own
              ? 'border-border bg-surface-subtle'
              : 'border-border bg-surface',
        )}
      >
        <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5">
          <span className="inline-flex items-center gap-1 text-label font-medium text-foreground">
            {ai ? <Bot aria-hidden="true" className="size-3.5 text-provenance-ai" /> : null}
            {name}
          </span>
          <time className="font-num text-caption text-muted-foreground">{message.at}</time>
          {message.channel ? <ChannelBadge channel={message.channel} /> : null}
        </div>
        <div className="text-small leading-relaxed text-foreground">{message.body}</div>
      </div>
    </li>
  )
}

export interface FeedbackThreadProps {
  messages: ThreadMessageView[]
  className?: string
}

export function FeedbackThread({ messages, className }: FeedbackThreadProps) {
  if (messages.length === 0) {
    return <p className={cn('text-small text-muted-foreground', className)}>Сообщений пока нет.</p>
  }
  return (
    <ol className={cn('space-y-2', className)}>
      {messages.map((message) => (
        <ThreadMessage key={message.id} message={message} />
      ))}
    </ol>
  )
}

/*
 * Persistent indicator of new, not-yet-seen feedback — visible without relying
 * on a push notification.
 */
export function FeedbackAttention({
  label = 'Новая обратная связь',
  className,
}: {
  label?: string
  className?: string
}) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full bg-unread px-2.5 py-1 text-caption font-medium text-unread-foreground',
        className,
      )}
    >
      <span aria-hidden="true" className="size-2 rounded-full bg-current" />
      {label}
    </span>
  )
}
