import { ArrowRight, Clock3 } from 'lucide-react'
import type { ReactNode } from 'react'

import { Badge, Button, Card, CardContent, CardDescription, CardHeader, CardTitle } from '@vmsh/ui'

export interface PrototypeCard {
  title: string
  description: string
  meta?: string
  status?: 'default' | 'success' | 'warning' | 'info'
  action?: string
}

export interface PrototypePageProps {
  eyebrow?: string
  title: string
  description: string
  actions?: ReactNode
  cards?: PrototypeCard[]
  children?: ReactNode
}

const statusClasses = {
  default: '',
  success: 'border-l-4 border-l-status-success',
  warning: 'border-l-4 border-l-status-warning',
  info: 'border-l-4 border-l-status-info',
} as const

export function PrototypePage({
  eyebrow,
  title,
  description,
  actions,
  cards = [],
  children,
}: PrototypePageProps) {
  return (
    <div className="mx-auto w-full max-w-6xl p-4 sm:p-6 lg:p-8">
      <div className="mb-7 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div className="max-w-3xl">
          {eyebrow ? (
            <p className="mb-1 text-xs font-medium tracking-wide text-primary uppercase">
              {eyebrow}
            </p>
          ) : null}
          <h1 className="text-balance text-2xl font-semibold tracking-tight sm:text-3xl">
            {title}
          </h1>
          <p className="mt-2 text-pretty text-sm leading-6 text-muted-foreground sm:text-base">
            {description}
          </p>
        </div>
        {actions ? <div className="flex shrink-0 flex-wrap gap-2">{actions}</div> : null}
      </div>

      {cards.length ? (
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {cards.map((card) => (
            <Card className={statusClasses[card.status ?? 'default']} key={card.title}>
              <CardHeader>
                <div className="flex items-start justify-between gap-3">
                  <CardTitle>{card.title}</CardTitle>
                  {card.status && card.status !== 'default' ? (
                    <Badge variant="outline">{card.status}</Badge>
                  ) : null}
                </div>
                <CardDescription>{card.description}</CardDescription>
              </CardHeader>
              <CardContent className="flex items-center justify-between gap-3">
                {card.meta ? (
                  <span className="flex items-center gap-1 text-xs text-muted-foreground">
                    <Clock3 className="size-3.5" aria-hidden="true" /> {card.meta}
                  </span>
                ) : (
                  <span />
                )}
                {card.action ? (
                  <Button size="sm" variant="ghost">
                    {card.action} <ArrowRight aria-hidden="true" />
                  </Button>
                ) : null}
              </CardContent>
            </Card>
          ))}
        </div>
      ) : null}

      {children ? <div className={cards.length ? 'mt-6' : undefined}>{children}</div> : null}
    </div>
  )
}
