import * as React from 'react'
import { Input as InputPrimitive } from '@base-ui/react/input'

import { cn } from '@vmsh/ui/lib/utils'

function Input({ className, type, ...props }: React.ComponentProps<'input'>) {
  const fileInput = type === 'file'

  return (
    <InputPrimitive
      type={type}
      data-slot="input"
      className={cn(
        'min-h-(--touch-target) w-full min-w-0 rounded-md border border-input bg-surface px-3 py-1 text-base transition-colors outline-none placeholder:text-placeholder focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/40 disabled:pointer-events-none disabled:cursor-not-allowed disabled:bg-muted disabled:opacity-60 aria-invalid:border-destructive aria-invalid:ring-3 aria-invalid:ring-destructive/25 md:text-sm',
        fileInput &&
          'cursor-pointer p-1 text-sm text-muted-foreground file:mr-3 file:inline-flex file:h-[calc(var(--touch-target)-0.5rem)] file:cursor-pointer file:items-center file:rounded-[min(var(--radius-md),10px)] file:border-0 file:bg-primary file:px-3 file:text-sm file:font-medium file:text-primary-foreground hover:file:bg-primary/80 disabled:file:cursor-not-allowed',
        className,
      )}
      {...props}
    />
  )
}

export { Input }
