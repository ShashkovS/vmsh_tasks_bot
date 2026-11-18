import { ChevronUp } from 'lucide-react'

import { Button } from '@vmsh/ui'

/**
 * Trailing collapse control for the inline task panels (answer, questions,
 * hint, solution). A long revealed panel pushes its own trigger off screen, so
 * every reveal repeats the close action at its end.
 */
export function StudentCollapseAction({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <div className="mt-2 font-sans">
      <Button onClick={onClick} size="sm" variant="ghost">
        <ChevronUp aria-hidden="true" />
        {label}
      </Button>
    </div>
  )
}
