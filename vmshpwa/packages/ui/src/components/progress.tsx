import { Progress as ProgressPrimitive } from '@base-ui/react/progress'

import { cn } from '@vmsh/ui/lib/utils'

/*
 * Determinate progress (photo compression, upload). The consumer supplies an
 * accessible name via `aria-label`; `value` is 0–100 (or null for waiting).
 */
function Progress({
  className,
  value,
  ...props
}: ProgressPrimitive.Root.Props & { className?: string }) {
  return (
    <ProgressPrimitive.Root data-slot="progress" value={value} {...props}>
      <ProgressPrimitive.Track
        className={cn(
          'relative h-1.5 w-full overflow-hidden rounded-full bg-surface-sunken',
          className,
        )}
      >
        <ProgressPrimitive.Indicator className="h-full rounded-full bg-primary transition-all duration-(--duration-normal) ease-(--ease-standard)" />
      </ProgressPrimitive.Track>
    </ProgressPrimitive.Root>
  )
}

export { Progress }
