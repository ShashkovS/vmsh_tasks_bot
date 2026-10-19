import * as React from 'react'

import { cn } from '@vmsh/ui/lib/utils'

// The shared primitive receives its association through `htmlFor` or nested
// controls at the call site, which static analysis cannot see in this wrapper.
/* eslint-disable jsx-a11y/label-has-associated-control */
function Label({ className, ...props }: React.ComponentProps<'label'>) {
  return (
    <label
      data-slot="label"
      className={cn(
        'flex items-center gap-2 text-sm leading-none font-medium select-none group-data-[disabled=true]:pointer-events-none group-data-[disabled=true]:opacity-50 peer-disabled:cursor-not-allowed peer-disabled:opacity-50',
        className,
      )}
      {...props}
    />
  )
}

export { Label }
