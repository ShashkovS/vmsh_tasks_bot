import * as React from 'react'
import { cva, type VariantProps } from 'class-variance-authority'

import { cn } from '@vmsh/ui/lib/utils'

/*
 * Presentational alert / banner (connection, sync, form-level notice). Meaning
 * is carried by the title and icon; tone colour only assists. Text stays
 * `foreground` for readability; tone lives on the border and the icon.
 */
const alertVariants = cva(
  'relative flex w-full items-start gap-2.5 rounded-md border px-3 py-2.5 text-sm [&>svg]:mt-0.5 [&>svg]:size-4 [&>svg]:shrink-0',
  {
    variants: {
      tone: {
        neutral: 'border-border bg-surface-subtle text-foreground [&>svg]:text-muted-foreground',
        info: 'border-status-info-border bg-status-info-surface text-foreground [&>svg]:text-status-info',
        success:
          'border-status-success-border bg-status-success-surface text-foreground [&>svg]:text-status-success',
        warning:
          'border-status-warning-border bg-status-warning-surface text-foreground [&>svg]:text-status-warning',
        danger:
          'border-status-danger-border bg-status-danger-surface text-foreground [&>svg]:text-status-danger',
      },
    },
    defaultVariants: { tone: 'neutral' },
  },
)

function Alert({
  className,
  tone,
  role = 'status',
  ...props
}: React.ComponentProps<'div'> & VariantProps<typeof alertVariants>) {
  return (
    <div
      role={role}
      data-slot="alert"
      className={cn(alertVariants({ tone }), className)}
      {...props}
    />
  )
}

function AlertContent({ className, ...props }: React.ComponentProps<'div'>) {
  return <div data-slot="alert-content" className={cn('min-w-0 flex-1', className)} {...props} />
}

function AlertTitle({ className, ...props }: React.ComponentProps<'div'>) {
  return <div data-slot="alert-title" className={cn('font-medium', className)} {...props} />
}

function AlertDescription({ className, ...props }: React.ComponentProps<'p'>) {
  return (
    <p
      data-slot="alert-description"
      className={cn('mt-0.5 text-muted-foreground', className)}
      {...props}
    />
  )
}

export { Alert, AlertContent, AlertTitle, AlertDescription, alertVariants }
