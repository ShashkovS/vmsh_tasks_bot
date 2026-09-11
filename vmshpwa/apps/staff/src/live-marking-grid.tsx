import { memo, useRef, useLayoutEffect, useCallback } from 'react'
import { useVirtualizer } from '@tanstack/react-virtual'
import type { LiveBoard } from '@vmsh/contracts'
import { cn } from '@vmsh/ui'
import { BookOpen } from 'lucide-react'

// live-marking.md: dense touch table, fixed names/header, independent authorship
// and pending/change indicators. Both routes use the same cell interaction.
export interface MarkDisplay {
  symbol: string
  mine: boolean
  changed: boolean
  pending?: 'draft' | 'queued' | 'sending' | 'conflict' | 'failed' | undefined
  disabled: boolean
}
export const LiveMarkButton = memo(
  function LiveMarkButton({
    label,
    display,
    onMark,
    studentId,
    problemId,
  }: {
    label: string
    display: MarkDisplay
    studentId: string
    problemId: string
    onMark: (studentId: string, problemId: string) => void
  }) {
    const status =
      display.pending === 'conflict'
        ? 'Конфликт'
        : display.pending === 'failed'
          ? 'Ошибка'
          : display.pending
            ? 'Не отправлено'
            : 'Сохранено'
    return (
      <button
        type="button"
        onClick={() => onMark(studentId, problemId)}
        disabled={display.disabled}
        aria-label={`${label}: ${display.symbol || 'пусто'}${display.mine ? ', моя оценка' : ''}, ${status}`}
        title={`${display.mine ? 'Моя оценка. ' : ''}${display.changed ? 'Изменено в этом приёме. ' : ''}${status}`}
        className={cn(
          'relative flex h-full min-h-11 w-full min-w-11 items-center justify-center border border-transparent text-2xl font-medium tabular-nums outline-none transition-colors hover:bg-accent focus-visible:z-20 focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-wait',
          display.mine && 'bg-primary/10 font-bold text-primary',
          display.changed && 'border-primary',
          display.pending && 'border-dashed border-status-warning',
          (display.pending === 'conflict' || display.pending === 'failed') &&
            'bg-destructive/10 text-destructive',
        )}
      >
        {display.symbol || (
          <span className="text-muted-foreground/40" aria-hidden="true">
            ·
          </span>
        )}
        {display.mine ? (
          <span className="absolute bottom-0.5 left-1 text-[8px] leading-none" aria-hidden="true">
            я
          </span>
        ) : null}
        {display.pending ? (
          <span className="absolute right-1 top-0.5 text-[10px] leading-none" aria-hidden="true">
            {display.pending === 'conflict' ? '!' : '○'}
          </span>
        ) : null}
      </button>
    )
  },
  (a, b) =>
    a.label === b.label &&
    a.studentId === b.studentId &&
    a.problemId === b.problemId &&
    a.onMark === b.onMark &&
    a.display.symbol === b.display.symbol &&
    a.display.mine === b.display.mine &&
    a.display.changed === b.display.changed &&
    a.display.pending === b.display.pending &&
    a.display.disabled === b.display.disabled,
)

// Stable events let memoized cells skip unrelated classmates' updates. The
// committed callback is refreshed before browser input can run (live-marking.md).
function useMarkAction(action: LiveSchoolGridProps['onMark']) {
  const current = useRef(action)
  useLayoutEffect(() => {
    current.current = action
  }, [action])
  return useCallback(
    (studentId: string, problemId: string) => current.current(studentId, problemId),
    [],
  )
}
const attendanceText = { unmarked: 'Не отмечен', present: 'Пришёл', absent: 'Отсутствует' }
const attendanceSymbol = { unmarked: '○', present: '✓', absent: '−' }
export interface LiveSchoolGridProps {
  board: LiveBoard
  expanded: string | null
  onExpand: (id: string) => void
  display: (studentId: string, problemId: string) => MarkDisplay
  onMark: (studentId: string, problemId: string) => void
  onAttendance: (studentId: string) => void
  attendance: (studentId: string) => {
    value: 'unmarked' | 'present' | 'absent'
    pending: boolean
    disabled: boolean
  }
}
export function LiveSchoolGrid({
  board,
  expanded,
  onExpand,
  display,
  onMark,
  onAttendance,
  attendance,
}: LiveSchoolGridProps) {
  const mark = useMarkAction(onMark)
  const scroll = useRef<HTMLDivElement>(null)
  // TanStack Virtual owns measurement; keep this hook outside compiler memoization.
  // eslint-disable-next-line react-hooks/incompatible-library
  const virtual = useVirtualizer({
    count: board.students.length,
    getScrollElement: () => scroll.current,
    estimateSize: (index) => (board.students[index]?.studentId === expanded ? 88 : 44),
    overscan: 8,
    getItemKey: (index) => board.students[index]?.studentId ?? index,
  })
  const items = virtual.getVirtualItems()
  const before = items[0]?.start ?? 0
  const after = items.length ? virtual.getTotalSize() - items[items.length - 1]!.end : 0
  return (
    <div
      ref={scroll}
      className="min-h-0 flex-1 overflow-auto overscroll-contain"
      aria-label="Таблица очного занятия"
    >
      <table className="w-max border-separate border-spacing-0 text-sm">
        <thead className="sticky top-0 z-30 bg-background">
          <tr>
            <th
              scope="col"
              className="sticky left-0 z-30 w-28 min-w-28 max-w-28 border-b border-r bg-background px-1 py-2 text-left text-xs sm:w-40 sm:min-w-40 sm:max-w-40 sm:px-2 sm:text-sm"
            >
              Школьник
            </th>
            <th scope="col" className="border-b border-r px-1 text-xs font-normal">
              Пришёл
            </th>
            {board.problems.map((p) => (
              <th
                scope="col"
                key={p.problemId}
                title={p.title}
                className="h-11 min-w-11 border-b border-r px-1 text-center font-semibold"
              >
                {p.label}
                <span className="block w-24 whitespace-normal break-words pb-1 text-xs font-normal leading-tight text-muted-foreground">
                  {p.title}
                </span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {before > 0 ? (
            <tr aria-hidden="true">
              <td colSpan={board.problems.length + 2} style={{ height: before }} />
            </tr>
          ) : null}
          {items.map((item) => {
            const student = board.students[item.index]!
            const att = attendance(student.studentId)
            return (
              <tr
                key={student.studentId}
                data-index={item.index}
                ref={virtual.measureElement}
                aria-selected={expanded === student.studentId}
              >
                <th
                  scope="row"
                  className={cn(
                    'sticky left-0 z-20 w-28 min-w-28 max-w-28 border-b border-r bg-background p-0 text-left sm:w-40 sm:min-w-40 sm:max-w-40',
                    expanded === student.studentId && 'bg-accent',
                  )}
                >
                  <button
                    type="button"
                    className="flex min-h-11 w-28 max-w-28 flex-col justify-center break-words px-1 py-1 text-left text-xs font-medium leading-tight sm:w-40 sm:max-w-40 sm:px-2 sm:text-sm sm:font-semibold focus-visible:ring-2 focus-visible:ring-ring"
                    style={{ minHeight: expanded === student.studentId ? 88 : 44 }}
                    onClick={() => onExpand(student.studentId)}
                    aria-expanded={expanded === student.studentId}
                  >
                    {student.displayName}
                    {expanded === student.studentId ? (
                      <span className="mt-1 text-xs font-normal text-muted-foreground">
                        {student.grade ? `${student.grade} кл. · ` : ''}
                        {student.middleName}
                      </span>
                    ) : null}
                  </button>
                </th>
                <td className="border-b border-r p-0">
                  <button
                    type="button"
                    disabled={att.disabled}
                    onClick={() => onAttendance(student.studentId)}
                    className={cn(
                      'h-full min-h-11 min-w-11 text-xl focus-visible:ring-2 focus-visible:ring-ring',
                      att.value === 'present' && 'bg-primary/10 text-primary',
                      att.pending && 'border border-dashed border-status-warning',
                    )}
                    aria-label={`${student.displayName}: ${attendanceText[att.value]}`}
                  >
                    {attendanceSymbol[att.value]}
                  </button>
                </td>
                {board.problems.map((p) => (
                  <td key={p.problemId} className="min-w-11 border-b border-r p-0">
                    <LiveMarkButton
                      label={`${student.displayName}, задача ${p.label}`}
                      display={display(student.studentId, p.problemId)}
                      onMark={mark}
                      studentId={student.studentId}
                      problemId={p.problemId}
                    />
                  </td>
                ))}
              </tr>
            )
          })}
          {after > 0 ? (
            <tr aria-hidden="true">
              <td colSpan={board.problems.length + 2} style={{ height: after }} />
            </tr>
          ) : null}
        </tbody>
      </table>
      {board.students.length === 0 ? (
        <p className="p-4 text-sm text-muted-foreground">В этом списке пока нет школьников.</p>
      ) : null}
    </div>
  )
}

// docs/task-titles.md: visible names, compact cards and two independent 44px actions.
// Tasks follow publication order; subparts keep their full label when wrapping.
export function LiveZoomGrid({
  board,
  display,
  onMark,
  onCondition,
}: Pick<LiveSchoolGridProps, 'board' | 'display' | 'onMark'> & {
  onCondition: (problem: LiveBoard['problems'][number]) => void
}) {
  const mark = useMarkAction(onMark)
  const student = board.students[0]
  if (!student) return <p className="p-4">Школьник не найден.</p>
  return (
    <div
      className="min-h-0 flex-1 overflow-auto overscroll-contain p-2"
      aria-label="Оценки школьника"
    >
      <div className="grid grid-cols-[repeat(auto-fill,minmax(5.625rem,1fr))] content-start gap-1">
        {board.problems.map((p) => (
          <div
            key={p.problemId}
            className="flex min-w-0 flex-col overflow-hidden rounded-md border"
          >
            <div
              className="flex-1 bg-muted px-1 text-center text-xs font-semibold leading-4"
              title={p.title}
            >
              {p.label}
              <span className="block break-words font-normal leading-tight text-muted-foreground">
                {p.title}
              </span>
            </div>
            <div className="flex h-11">
              <LiveMarkButton
                label={`Задача ${p.label}`}
                display={display(student.studentId, p.problemId)}
                onMark={mark}
                studentId={student.studentId}
                problemId={p.problemId}
              />
              <button
                type="button"
                className="flex h-11 w-11 shrink-0 items-center justify-center border-l text-muted-foreground hover:bg-accent focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"
                aria-label={`Показать условие задачи ${p.label}`}
                title="Показать условие"
                onClick={(event) => {
                  // Safari does not focus buttons on pointer click; restore this target after the dialog.
                  event.currentTarget.focus()
                  onCondition(p)
                }}
              >
                <BookOpen className="size-4" aria-hidden="true" />
              </button>
            </div>
          </div>
        ))}
      </div>
      {board.problems.length === 0 ? (
        <p className="p-4 text-sm text-muted-foreground">
          Устных задач нет. Переключитесь на «Все».
        </p>
      ) : null}
    </div>
  )
}
