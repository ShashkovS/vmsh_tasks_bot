import { Badge, cn } from '@vmsh/ui'

import { TaskTypeIcon } from './task-type'
import type { TaskListItemView } from './types'
import { VerdictMark } from './verdict-mark'

/*
 * One row of a problem sheet. Type is an icon (no repeated word); the graded
 * verdict is shown when review is finished, otherwise the current status. A
 * quiet «новое» marks unseen feedback. The whole row is one button.
 */
export interface TaskListItemProps {
  task: TaskListItemView
  onOpen?: (id: string) => void
  className?: string
}

export function TaskListItem({ task, onOpen, className }: TaskListItemProps) {
  return (
    <button
      className={cn(
        'flex w-full items-start gap-3 rounded-md border border-border bg-surface px-3 py-2.5 text-left transition-colors hover:bg-surface-subtle focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring',
        className,
      )}
      onClick={() => onOpen?.(task.id)}
      type="button"
    >
      <TaskTypeIcon className="mt-0.5" type={task.type} />
      <span className="min-w-0 flex-1">
        <span className="flex flex-wrap items-center gap-x-2 gap-y-1">
          <span className="font-num text-small font-medium text-muted-foreground">
            {task.number}
          </span>
          {task.verdict ? (
            <VerdictMark showLabel verdict={task.verdict} />
          ) : (
            <Badge variant={task.status.tone}>{task.status.label}</Badge>
          )}
          {task.hasNewFeedback ? (
            <span className="ml-auto inline-flex items-center gap-1 text-caption font-medium text-unread">
              <span aria-hidden="true" className="size-1.5 rounded-full bg-unread" />
              новое
            </span>
          ) : null}
        </span>
        <span className="mt-0.5 block font-medium text-foreground">{task.title}</span>
      </span>
    </button>
  )
}
