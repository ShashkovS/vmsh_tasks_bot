import { Bell } from 'lucide-react'

import { Badge, Card, CardContent, cn } from '@vmsh/ui'

export interface NotificationEventCardProps {
  title: string
  description: string
  occurredAt: string
  occurredAtDateTime?: string
  unread?: boolean
  href?: string
  className?: string
}

/** Compact account-scoped event row for Student and Family notification lists. */
export function NotificationEventCard({
  title,
  description,
  occurredAt,
  occurredAtDateTime,
  unread = false,
  href,
  className,
}: NotificationEventCardProps) {
  const content = (
    <CardContent className="flex items-start gap-3 p-3">
      <Bell aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
      <div className="min-w-0 flex-1 space-y-0.5">
        <div className="flex flex-wrap items-center gap-2">
          <p className="text-small font-medium text-foreground">{title}</p>
          {unread ? <Badge variant="info">Новое</Badge> : null}
        </div>
        <p className="text-small text-muted-foreground">{description}</p>
        <time
          className="block text-caption text-muted-foreground"
          dateTime={occurredAtDateTime ?? occurredAt}
        >
          {occurredAt}
        </time>
      </div>
    </CardContent>
  )
  return (
    <Card className={cn(unread && 'border-info/40', className)}>
      {href ? (
        <a className="block rounded-md focus-visible:outline-none focus-visible:ring-2" href={href}>
          {content}
        </a>
      ) : (
        content
      )}
    </Card>
  )
}
