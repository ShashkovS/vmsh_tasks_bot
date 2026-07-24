import { ArrowDown, ArrowUpDown } from 'lucide-react'

import { Button, Table, TableBody, TableCell, TableHead, TableHeader, TableRow, cn } from '@vmsh/ui'

import { LevelChip } from './level-chip'
import type { LevelView } from './types'

/*
 * Review queue — the main entrance to checking, by task. Shows the pending
 * count and how long work has waited, sorts by task / waiting / group / student,
 * keeps the full task title readable, offers a recheck for already-reviewed
 * work, and shows work held by others with their name and a disabled action.
 */
export interface ReviewQueueItem {
  id: string
  taskNumber: string
  taskTitle: string
  level: LevelView
  studentName: string
  groupName: string
  waitingLabel: string
  waitingMinutes: number
  busyBy?: string
  reviewed?: boolean
}

export type ReviewSort = 'task' | 'waiting' | 'group' | 'student'
export type ReviewMode = 'list' | 'fast'

export interface ReviewQueueProps {
  items: ReviewQueueItem[]
  sort: ReviewSort
  onSortChange: (sort: ReviewSort) => void
  mode?: ReviewMode
  onModeChange?: (mode: ReviewMode) => void
  onOpen?: (id: string) => void
  onRecheck?: (id: string) => void
  className?: string
}

function sortItems(items: ReviewQueueItem[], sort: ReviewSort): ReviewQueueItem[] {
  const copy = [...items]
  switch (sort) {
    case 'task':
      return copy.sort((a, b) => a.taskNumber.localeCompare(b.taskNumber, 'ru', { numeric: true }))
    case 'group':
      return copy.sort((a, b) => a.groupName.localeCompare(b.groupName, 'ru'))
    case 'student':
      return copy.sort((a, b) => a.studentName.localeCompare(b.studentName, 'ru'))
    case 'waiting':
      return copy.sort((a, b) => b.waitingMinutes - a.waitingMinutes)
  }
}

function SortHead({
  label,
  sortKey,
  active,
  onSortChange,
  className,
}: {
  label: string
  sortKey: ReviewSort
  active: ReviewSort
  onSortChange: (sort: ReviewSort) => void
  className?: string
}) {
  const isActive = active === sortKey
  return (
    <TableHead aria-sort={isActive ? 'ascending' : 'none'} className={className}>
      <button
        className="inline-flex items-center gap-1 font-medium text-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring"
        onClick={() => onSortChange(sortKey)}
        type="button"
      >
        {label}
        {isActive ? (
          <ArrowDown aria-hidden="true" className="size-3.5" />
        ) : (
          <ArrowUpDown aria-hidden="true" className="size-3.5 text-muted-foreground" />
        )}
      </button>
    </TableHead>
  )
}

export function ReviewQueue({
  items,
  sort,
  onSortChange,
  mode = 'list',
  onModeChange,
  onOpen,
  onRecheck,
  className,
}: ReviewQueueProps) {
  const sorted = sortItems(items, sort)
  const oldest = items.reduce((max, item) => Math.max(max, item.waitingMinutes), 0)

  return (
    <div className={cn('space-y-3', className)} data-density="staff">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-small text-muted-foreground" role="status">
          В очереди: <span className="font-medium text-foreground">{items.length}</span>
          {oldest > 0 ? `, дольше всех ждёт ${Math.floor(oldest / 60)} ч ${oldest % 60} мин` : ''}
        </p>
        {onModeChange ? (
          <div className="inline-flex overflow-hidden rounded-md border border-border">
            {(['list', 'fast'] as ReviewMode[]).map((value) => (
              <button
                aria-pressed={mode === value}
                className={cn(
                  'px-3 py-1 text-small focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring',
                  mode === value
                    ? 'bg-primary/10 font-medium text-foreground'
                    : 'text-muted-foreground hover:bg-surface-subtle',
                )}
                key={value}
                onClick={() => onModeChange(value)}
                type="button"
              >
                {value === 'list' ? 'Список' : 'По одной'}
              </button>
            ))}
          </div>
        ) : null}
      </div>

      <div className="overflow-x-auto rounded-md border border-border">
        <Table>
          <TableHeader>
            <TableRow>
              <SortHead active={sort} label="Задача" onSortChange={onSortChange} sortKey="task" />
              <TableHead>Уровень</TableHead>
              <SortHead active={sort} label="Группа" onSortChange={onSortChange} sortKey="group" />
              <SortHead
                active={sort}
                label="Ученик"
                onSortChange={onSortChange}
                sortKey="student"
              />
              <SortHead active={sort} label="Ждёт" onSortChange={onSortChange} sortKey="waiting" />
              <TableHead className="text-right">Действие</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {sorted.map((item) => (
              <TableRow key={item.id}>
                <TableCell>
                  <span className="font-num font-medium text-foreground">{item.taskNumber}</span>{' '}
                  <span className="text-muted-foreground">{item.taskTitle}</span>
                </TableCell>
                <TableCell>
                  <LevelChip compact level={item.level} />
                </TableCell>
                <TableCell className="text-muted-foreground">{item.groupName}</TableCell>
                <TableCell className="text-foreground">{item.studentName}</TableCell>
                <TableCell className="font-num text-muted-foreground">
                  {item.waitingLabel}
                </TableCell>
                <TableCell className="text-right">
                  {item.busyBy ? (
                    <span className="text-caption text-muted-foreground">
                      Проверяет {item.busyBy}
                    </span>
                  ) : item.reviewed ? (
                    <Button onClick={() => onRecheck?.(item.id)} size="xs" variant="ghost">
                      Перепроверить
                    </Button>
                  ) : (
                    <Button onClick={() => onOpen?.(item.id)} size="xs" variant="outline">
                      Открыть
                    </Button>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}
