import { CircleAlert, Inbox, LockKeyhole, RefreshCw, WifiOff } from 'lucide-react'
import type { ReactNode } from 'react'

import { Button, Card, CardContent, Skeleton, cn } from '@vmsh/ui'

/*
 * Page composition contract for dev/design-system/05-pages-and-flows.md.
 * Audience pages own their data and routes; PageLayout/PageStatePanel only keep
 * headings, responsive measure, and loading/empty/error/offline/forbidden states
 * consistent. Page stories in apps/{student,family,staff}/src/pages.stories.tsx
 * are the proof.
 */
export interface PageLayoutProps {
  eyebrow?: ReactNode
  title: string
  description?: ReactNode
  actions?: ReactNode
  children: ReactNode
  width?: 'reading' | 'content' | 'wide'
  className?: string
}

const widthClass = {
  reading: 'max-w-3xl',
  content: 'max-w-5xl',
  wide: 'max-w-[1500px]',
} as const

export function PageLayout({
  eyebrow,
  title,
  description,
  actions,
  children,
  width = 'content',
  className,
}: PageLayoutProps) {
  return (
    <div className={cn('mx-auto w-full px-4 py-5 sm:px-6 sm:py-7', widthClass[width], className)}>
      <div className="mb-5 flex flex-col gap-3 border-b border-border pb-4 sm:flex-row sm:items-end sm:justify-between">
        <div className="min-w-0 space-y-1">
          {eyebrow ? (
            <div className="text-caption font-medium tracking-wide text-muted-foreground">
              {eyebrow}
            </div>
          ) : null}
          <h1 className="text-balance text-title font-semibold tracking-tight text-foreground">
            {title}
          </h1>
          {description ? (
            <div className="max-w-3xl text-small leading-relaxed text-muted-foreground">
              {description}
            </div>
          ) : null}
        </div>
        {actions ? <div className="flex shrink-0 flex-wrap gap-2">{actions}</div> : null}
      </div>
      {children}
    </div>
  )
}

export function PageSection({
  title,
  description,
  action,
  children,
  className,
}: {
  title: string
  description?: ReactNode
  action?: ReactNode
  children: ReactNode
  className?: string
}) {
  return (
    <section className={cn('space-y-3', className)}>
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h2 className="text-subtitle font-semibold text-foreground">{title}</h2>
          {description ? (
            <div className="mt-0.5 text-caption text-muted-foreground">{description}</div>
          ) : null}
        </div>
        {action}
      </div>
      {children}
    </section>
  )
}

export type PageDisplayState = 'ready' | 'loading' | 'empty' | 'error' | 'offline' | 'forbidden'

const stateIcon = {
  empty: Inbox,
  error: CircleAlert,
  offline: WifiOff,
  forbidden: LockKeyhole,
} as const

export function PageStatePanel({
  state,
  title,
  description,
  actionLabel,
  onAction,
}: {
  state: Exclude<PageDisplayState, 'ready'>
  title?: string
  description?: string
  actionLabel?: string | undefined
  onAction?: (() => void) | undefined
}) {
  if (state === 'loading') {
    return (
      <Card aria-label="Загрузка" role="status">
        <CardContent className="space-y-3 pt-5">
          <Skeleton className="h-5 w-2/5" />
          <Skeleton className="h-16 w-full" />
          <Skeleton className="h-16 w-full" />
          <span className="sr-only">Загружаем данные</span>
        </CardContent>
      </Card>
    )
  }

  const Icon = stateIcon[state]
  const defaults = {
    empty: ['Здесь пока ничего нет', 'Новые материалы появятся здесь автоматически.'],
    error: [
      'Не удалось загрузить данные',
      'Ваши локальные изменения сохранены. Попробуйте ещё раз.',
    ],
    offline: ['Нет сети', 'Доступно всё, что уже сохранено на этом устройстве.'],
    forbidden: ['Нет доступа', 'У вашей учётной записи нет права открывать этот раздел.'],
  } as const

  return (
    <Card role={state === 'error' ? 'alert' : 'status'}>
      <CardContent className="flex gap-3 pt-5">
        <Icon aria-hidden="true" className="mt-0.5 size-5 shrink-0 text-muted-foreground" />
        <div className="min-w-0 space-y-2">
          <div>
            <h2 className="font-medium text-foreground">{title ?? defaults[state][0]}</h2>
            <p className="mt-1 text-small text-muted-foreground">
              {description ?? defaults[state][1]}
            </p>
          </div>
          {actionLabel && onAction ? (
            <Button onClick={onAction} size="sm" variant="outline">
              <RefreshCw aria-hidden="true" />
              {actionLabel}
            </Button>
          ) : null}
        </div>
      </CardContent>
    </Card>
  )
}
