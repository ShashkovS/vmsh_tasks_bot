import { Bell } from 'lucide-react'
import { useId } from 'react'

import { Button, cn } from '@vmsh/ui'

/*
 * Explains what notifications are for BEFORE triggering the browser prompt, so
 * the one system prompt is asked in context. A refusal is respected — «Не
 * сейчас» dismisses without nagging.
 */
export interface PushCategory {
  id: string
  label: string
  description?: string
}

export interface PushPermissionCardProps {
  categories: PushCategory[]
  onEnable?: () => void
  onDismiss?: () => void
  className?: string
}

export function PushPermissionCard({
  categories,
  onEnable,
  onDismiss,
  className,
}: PushPermissionCardProps) {
  const titleId = useId()
  return (
    <section
      aria-labelledby={titleId}
      className={cn('space-y-3 rounded-lg border border-border bg-surface p-4', className)}
    >
      <div className="flex items-start gap-3">
        <Bell aria-hidden="true" className="mt-0.5 size-5 shrink-0 text-muted-foreground" />
        <div className="space-y-1">
          <h2 className="text-label font-medium text-foreground" id={titleId}>
            Уведомления
          </h2>
          <p className="text-small text-muted-foreground">
            Разрешение у браузера спросим только после вашего согласия. Сообщать можем о:
          </p>
        </div>
      </div>

      <ul className="space-y-1.5 pl-8">
        {categories.map((category) => (
          <li className="text-small text-foreground" key={category.id}>
            <span className="font-medium">{category.label}</span>
            {category.description ? (
              <span className="text-muted-foreground"> — {category.description}</span>
            ) : null}
          </li>
        ))}
      </ul>

      <div className="flex gap-2 pl-8">
        <Button onClick={onEnable} size="sm">
          Включить уведомления
        </Button>
        <Button onClick={onDismiss} size="sm" variant="ghost">
          Не сейчас
        </Button>
      </div>
    </section>
  )
}
