import { Bot, Cog, Send, Smartphone } from 'lucide-react'
import type { ReactNode } from 'react'

import { cn } from '@vmsh/ui'

/*
 * Feedback thread linking pointwise annotations and text messages. Each message
 * shows author, time and channel; AI feedback is a distinct author and can
 * never be confused with a live teacher. Asymmetric visibility is a permission
 * concern — a Student/Family view-model simply never contains hidden messages.
 */
export type ThreadAuthorKind = 'student' | 'teacher' | 'admin' | 'ai' | 'system'
export type ThreadChannel = 'pwa' | 'telegram' | 'staff' | 'system'

export interface ThreadMessageView {
  id: string
  author: { kind: ThreadAuthorKind; name?: string }
  at: string
  channel?: ThreadChannel
  /** Concrete source retained when synonymous task branches are shown together. */
  origin?: { courseName: string; groupName: string; taskNumber: string }
  body: ReactNode
  /** True for the viewer's own message (aligned to the trailing edge). */
  own?: boolean
}

const authorName: Record<ThreadAuthorKind, string> = {
  student: 'Ученик',
  teacher: 'Преподаватель',
  admin: 'Администратор',
  ai: 'ИИ',
  system: 'Система',
}

const channelView = {
  pwa: { icon: Smartphone, label: 'в приложении' },
  telegram: { icon: Send, label: 'через Telegram' },
  system: { icon: Cog, label: 'системное событие' },
} as const

function ChannelBadge({ channel }: { channel: Exclude<ThreadChannel, 'staff'> }) {
  const { icon: Icon, label } = channelView[channel]
  return (
    <span className="inline-flex items-center gap-1 text-caption text-muted-foreground">
      <Icon aria-hidden="true" className="size-3.5" />
      {label}
    </span>
  )
}

export function ThreadMessage({ message }: { message: ThreadMessageView }) {
  const ai = message.author.kind === 'ai'
  const system = message.author.kind === 'system'
  const name = message.author.name ?? authorName[message.author.kind]
  return (
    <li className={cn('flex', message.own && 'justify-end')}>
      <div
        className={cn(
          'max-w-[85%] space-y-1 rounded-lg border px-3 py-2',
          ai
            ? 'border-dashed border-provenance-ai-border bg-provenance-ai-surface'
            : system
              ? 'border-dashed border-border bg-surface-subtle'
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
          {message.channel && message.channel !== 'staff' ? (
            <ChannelBadge channel={message.channel} />
          ) : null}
        </div>
        {message.origin ? (
          <p className="text-caption text-muted-foreground">
            {message.origin.courseName} · {message.origin.groupName} · {message.origin.taskNumber}
          </p>
        ) : null}
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
