import { useCallback, useEffect, useMemo, useRef, useState, useSyncExternalStore } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Undo2, UserPlus, Search, ArrowLeft, Check, X, ChevronDown } from 'lucide-react'

import {
  createLiveMarkingClient,
  PageStatePanel,
  useAuthenticatedPrincipal,
  useAuthentication,
  useRealtimeConnection,
} from '@vmsh/app-shell'
import {
  LIVE_REACTIONS,
  liveCellSchema,
  type LiveContext,
  type LiveCommand,
  type LiveReceipt,
  type LiveCells,
  type LiveDirectoryStudent,
  type LiveBoard,
} from '@vmsh/contracts'
import { LiveMarkingDatabase, LiveMarkingQueue } from '@vmsh/offline'
import {
  Button,
  Input,
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@vmsh/ui'
import { studentNameMatchesSearch } from './student-directory-search'
import { liveCellKey, emptyLiveCell, mergeLiveCells, type LiveSearch } from './live-marking-state'
import { LiveSchoolGrid, LiveZoomGrid, type MarkDisplay } from './live-marking-grid'
import { LiveConditionDialog } from './live-marking-condition'

// Page composition: live-marking.md and design-system/05-pages-and-flows.md.

function StudentSearch({
  students,
  onSelect,
  transfer,
}: {
  students: LiveDirectoryStudent[]
  onSelect: (student: LiveDirectoryStudent) => void
  transfer: boolean
}) {
  const [query, setQuery] = useState('')
  const input = useRef<HTMLInputElement>(null)
  useEffect(() => {
    input.current?.focus()
  }, [])
  const matches = useMemo(
    () =>
      query.trim()
        ? students
            .filter((s) =>
              studentNameMatchesSearch(`${s.displayName} ${s.middleName ?? ''}`, query),
            )
            .slice(0, 30)
        : [],
    [students, query],
  )
  return (
    <div className="flex min-h-0 flex-1 flex-col gap-2">
      <Input
        ref={input}
        aria-label="Поиск школьника"
        placeholder="Фамилия или имя…"
        type="search"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        className="min-h-11"
      />
      <div className="min-h-0 overflow-auto" aria-live="polite">
        {matches.map((s) => (
          <button
            key={s.studentId}
            type="button"
            onClick={() => onSelect(s)}
            className="flex min-h-14 w-full flex-col gap-0.5 border-b p-2 text-left hover:bg-accent focus-visible:ring-2 focus-visible:ring-ring"
          >
            <span className="font-semibold">{s.displayName}</span>
            <span className="text-xs text-muted-foreground">
              {[
                s.grade ? `${s.grade} кл.` : null,
                s.middleName,
                s.groupName,
                transfer ? (s.attendanceMode === 'online' ? 'Онлайн' : 'Очно') : null,
              ]
                .filter(Boolean)
                .join(' · ')}
            </span>
            {transfer ? (
              <span className="text-xs text-muted-foreground">
                {s.rooms
                  .slice(0, 3)
                  .map(
                    (r) =>
                      `${r.roomName ?? 'Без аудитории'} (${new Date(r.startsAt).toLocaleDateString('ru-RU')})`,
                  )
                  .join(' ← ') || 'Назначений ещё нет'}
              </span>
            ) : null}
          </button>
        ))}
        {query && matches.length === 0 ? (
          <p className="p-3 text-sm text-muted-foreground">
            Никого не нашли. Попробуйте другую часть имени.
          </p>
        ) : null}
        {!query ? (
          <p className="p-3 text-sm text-muted-foreground">Введите фамилию или имя школьника.</p>
        ) : null}
      </div>
    </div>
  )
}

export function LiveMarkingPage({
  mode,
  search,
  onSearch,
}: {
  mode: 'school' | 'zoom'
  search: LiveSearch
  onSearch: (search: LiveSearch) => void
}) {
  const authentication = useAuthentication()
  const principal = useAuthenticatedPrincipal()
  if (principal.audience !== 'staff') throw new Error('Staff only')
  const runtime = authentication.client.runtime
  const refresh = authentication.refresh
  const client = useMemo(() => createLiveMarkingClient(runtime, refresh), [runtime, refresh])
  const queryClient = useQueryClient()
  const accountId = principal.accountId
  const key = useCallback(
    (resource: string, scope?: unknown) => [resource, accountId, scope],
    [accountId],
  )
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [expanded, setExpanded] = useState<string | null>(null)
  const [findOpen, setFindOpen] = useState(false)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [conditionProblem, setConditionProblem] = useState<LiveBoard['problems'][number] | null>(
    null,
  )
  const [visitsOpen, setVisitsOpen] = useState(false)
  const [transferStudent, setTransferStudent] = useState<LiveDirectoryStudent | null>(null)
  const [skippedUndo, setSkippedUndo] = useState<string[]>([])
  const realtime = useRealtimeConnection()
  const allowed = principal.capabilities.includes('oral.manage')
  const catalog = useQuery({
    queryKey: key('live-catalog'),
    queryFn: client.catalog,
    enabled: allowed,
    meta: { realtimeResources: ['live-catalog', 'live-board'] },
  })
  const event =
    catalog.data?.events.find((e) => e.eventId === search.event) ??
    catalog.data?.events.find((e) => e.status === 'scheduled') ??
    catalog.data?.events[0]
  const room = event?.rooms.find((r) => r.roomId === search.room)
  const course =
    catalog.data?.courses.find(
      (c) => c.courseId === (mode === 'school' ? room?.courseId : search.course),
    ) ?? (mode === 'zoom' ? catalog.data?.courses[0] : undefined)
  const directory = useQuery({
    queryKey: key('live-directory', course?.courseId),
    queryFn: () => client.directory(course!.courseId),
    enabled: !!course,
    meta: { realtimeResources: ['live-directory'] },
    staleTime: 60_000,
  })
  const student = directory.data?.students.find((s) => s.studentId === search.student)
  const session =
    course?.sessions.find((s) => s.sessionId === search.session) ??
    course?.sessions.find((s) => !s.finishedAt)
  const lessons =
    course?.lessons.filter(
      (l) => l.groupId === (mode === 'school' ? room?.groupId : student?.groupId),
    ) ?? []
  const lesson =
    lessons.find((l) => l.lessonId === search.lesson) ??
    lessons.find((l) => mode === 'school' && l.lessonId === room?.lessonId) ??
    lessons[0]
  const spec: LiveContext | null =
    mode === 'school'
      ? event && room
        ? {
            mode,
            contextId: event.eventId,
            roomId: room.roomId,
            ...(lesson ? { lessonId: lesson.lessonId } : {}),
          }
        : null
      : session
        ? {
            mode,
            contextId: session.sessionId,
            ...(lesson ? { lessonId: lesson.lessonId } : {}),
            ...(student ? { studentId: student.studentId } : {}),
          }
        : null
  const boardEnabled = !!spec?.lessonId && (mode === 'school' || !!spec.studentId)
  const board = useQuery({
    queryKey: key('live-board', spec),
    queryFn: () => client.board(spec!),
    enabled: boardEnabled,
    meta: { realtimeResources: spec ? [`live-board/${spec.contextId}`] : [] },
  })
  const cells = useQuery({
    queryKey: key('live-cells', spec),
    queryFn: async () => {
      const previous = queryClient.getQueryData<LiveCells>(key('live-cells', spec))
      const current = await client.cells(
        spec!,
        realtime?.state.status === 'ready' ? previous : undefined,
      )
      const latest = queryClient.getQueryData<LiveCells>(key('live-cells', spec))
      return mergeLiveCells(current, latest)
    },
    enabled: boardEnabled,
    meta: { realtimeResources: spec ? [`live-cells/${spec.lessonId}`, 'review-queue'] : [] },
  })
  const history = useQuery({
    queryKey: key(
      'live-history',
      spec ? { mode: spec.mode, contextId: spec.contextId, roomId: spec.roomId } : null,
    ),
    queryFn: () => client.history(spec!),
    enabled: !!spec,
    meta: { realtimeResources: spec ? [`live-history/${spec.contextId}`] : [] },
  })
  const visits = useQuery({
    queryKey: key('live-visits', session?.sessionId),
    queryFn: () => client.visits(session!.sessionId),
    enabled: mode === 'zoom' && !!session,
    meta: { realtimeResources: session ? [`live-visits/${session.sessionId}`] : [] },
  })
  const received = useCallback(
    (receipt: LiveReceipt, command: LiveCommand) => {
      const parsed = liveCellSchema.safeParse(receipt.state)
      if (parsed.success && command.kind === 'mark')
        queryClient.setQueryData<LiveCells>(key('live-cells', command.context), (old) =>
          old ? mergeLiveCells({ ...old, cells: [parsed.data] }, old) : old,
        )
      void queryClient.invalidateQueries({
        predicate: (q) =>
          q.queryKey[1] === accountId &&
          [
            'live-history',
            'live-visits',
            ...(command.kind === 'mark' ? [] : ['live-board', 'live-directory']),
          ].includes(String(q.queryKey[0])),
      })
      if (!parsed.success || receipt.replayed || command.kind === 'undo')
        void queryClient.invalidateQueries({ queryKey: key('live-cells').slice(0, 2) })
    },
    [queryClient, key, accountId],
  )
  const queue = useMemo(
    () =>
      new LiveMarkingQueue(new LiveMarkingDatabase(runtime, accountId), client.execute, received),
    [runtime, accountId, client, received],
  )
  const queueState = useSyncExternalStore(queue.subscribe, queue.getSnapshot)
  useEffect(() => {
    void queue.hydrate()
    const flush = () => {
      void queue.flush()
    }
    const hidden = () => {
      if (document.visibilityState === 'hidden') flush()
    }
    window.addEventListener('online', flush)
    window.addEventListener('blur', flush)
    window.addEventListener('pagehide', flush)
    document.addEventListener('visibilitychange', hidden)
    return () => {
      void queue.flush()
      queue.stop()
      window.removeEventListener('online', flush)
      window.removeEventListener('blur', flush)
      window.removeEventListener('pagehide', flush)
      document.removeEventListener('visibilitychange', hidden)
    }
  }, [queue])
  const navigate = (next: LiveSearch) => {
    void queue.flush()
    setError(null)
    onSearch(next)
  }
  const action = async (fn: () => Promise<unknown>) => {
    setBusy(true)
    setError(null)
    try {
      await fn()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Не удалось выполнить действие')
      authentication.handleApiError(e)
    } finally {
      setBusy(false)
    }
  }
  const execute = async (command: LiveCommand) => {
    const receipt = await client.execute(command)
    received(receipt, command)
    return receipt
  }
  const historyOps = useMemo(() => history.data?.operations ?? [], [history.data])
  const undoTarget = historyOps.find((o) => !o.undone && !skippedUndo.includes(o.operationId))
  const undo = () => {
    if (!spec || busy) return
    if (queue.undoLocal(spec.contextId)) return
    if (!undoTarget) return
    void action(async () => {
      await execute({
        kind: 'undo',
        operationId: crypto.randomUUID(),
        context: spec,
        targetOperationId: undoTarget.operationId,
      })
    })
  }
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null
      if (
        (e.metaKey || e.ctrlKey) &&
        !e.shiftKey &&
        e.key.toLowerCase() === 'z' &&
        !target?.closest('input,textarea,[contenteditable="true"]')
      ) {
        e.preventDefault()
        undo()
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  })
  const cellMap = useMemo(
    () => new Map(cells.data?.cells.map((c) => [liveCellKey(c.studentId, c.problemId), c])),
    [cells.data],
  )
  const pendingMap = useMemo(
    () => new Map(queueState.entries.map((e) => [e.key, e])),
    [queueState.entries],
  )
  const selectedLessonId = lesson?.lessonId
  const changed = new Set(
    historyOps
      .filter((o) => !o.undone && o.kind === 'mark' && o.state.lessonId === selectedLessonId)
      .map((o) => liveCellKey(o.state.studentId, o.state.problemId ?? '')),
  )
  const markCommand = (
    studentId: string,
    problemId: string,
  ): Extract<LiveCommand, { kind: 'mark' }> => ({
    kind: 'mark',
    operationId: crypto.randomUUID(),
    context: spec!,
    studentId,
    problemId,
    expectedVersion: cellMap.get(liveCellKey(studentId, problemId))?.version ?? 0,
    value: 'plus',
  })
  const display = (studentId: string, problemId: string): MarkDisplay => {
    const cell =
      cellMap.get(liveCellKey(studentId, problemId)) ?? emptyLiveCell(studentId, problemId)
    const pending = pendingMap.get(`${mode}:${spec?.contextId}:${studentId}:${problemId}`)
    return {
      symbol:
        pending?.command.kind === 'mark'
          ? pending.command.value === 'plus'
            ? '+'
            : '−'
          : cell.symbol,
      mine: pending?.command.kind === 'mark' || cell.teacherId === principal.userId,
      changed: changed.has(liveCellKey(studentId, problemId)),
      pending: pending?.status,
      disabled:
        !!board.data?.readOnly ||
        !queueState.ready ||
        ['sending', 'conflict', 'failed'].includes(pending?.status ?? ''),
    }
  }
  const mark = (studentId: string, problemId: string) => {
    if (spec) queue.cycle(markCommand(studentId, problemId))
  }
  const attendance = (studentId: string) => {
    const s = board.data?.students.find((s) => s.studentId === studentId)
    const pending = pendingMap.get(`${mode}:${spec?.contextId}:${studentId}:attendance`)
    return {
      value:
        pending?.command.kind === 'attendance'
          ? pending.command.value
          : (s?.attendance ?? 'unmarked'),
      pending: !!pending,
      disabled:
        !queueState.ready || ['sending', 'conflict', 'failed'].includes(pending?.status ?? ''),
    }
  }
  const attend = (studentId: string) => {
    const s = board.data?.students.find((s) => s.studentId === studentId)
    if (spec && s)
      queue.cycle(
        {
          kind: 'attendance',
          operationId: crypto.randomUUID(),
          context: spec,
          studentId,
          expectedVersion: s.attendanceVersion,
          value: 'present',
        },
        s.attendance,
      )
  }
  const openStudent = (s: LiveDirectoryStudent) => {
    void action(async () => {
      await queue.flush()
      const targetSession = session ?? (await client.start(course!.courseId))
      const targetLesson = course?.lessons.find((l) => l.groupId === s.groupId)
      if (!targetLesson) {
        setError('У этой группы пока нет опубликованных занятий.')
        return
      }
      const next = {
        ...search,
        course: course!.courseId,
        session: targetSession.sessionId,
        student: s.studentId,
        lesson: targetLesson.lessonId,
      }
      await client.visit({
        mode: 'zoom',
        contextId: targetSession.sessionId,
        studentId: s.studentId,
        lessonId: targetLesson.lessonId,
      })
      await queryClient.invalidateQueries({ queryKey: key('live-catalog') })
      setFindOpen(false)
      navigate(next)
    })
  }
  const filterBoard: LiveBoard | undefined = board.data
    ? {
        ...board.data,
        students:
          mode === 'school' && search.presentOnly
            ? board.data.students.filter((s) => attendance(s.studentId).value === 'present')
            : board.data.students,
        problems:
          mode === 'zoom' && search.oralOnly !== false
            ? board.data.problems.filter((p) => p.oral)
            : board.data.problems,
      }
    : undefined
  const scopedPending = queueState.entries.filter(
    (e) => e.command.context.contextId === spec?.contextId,
  )
  const isOffline = realtime?.state.status !== 'ready'
  const compactStatus = scopedPending.length
    ? `${scopedPending.length} не отправлено`
    : isOffline
      ? 'Нет синхронизации'
      : 'Сохранено'

  const lessonPicker = lesson ? (
    <select
      aria-label="Занятие"
      value={lesson.lessonId}
      className="h-11 rounded-md border bg-background px-2 text-sm"
      onChange={(e) => navigate({ ...search, lesson: e.target.value })}
    >
      {lessons.map((l) => (
        <option key={l.lessonId} value={l.lessonId}>
          Занятие {l.number}
        </option>
      ))}
    </select>
  ) : null
  const schoolSettings = (
    <>
      <select
        aria-label="Очное событие"
        className="h-11 max-w-44 rounded-md border bg-background px-2 text-sm"
        value={event?.eventId ?? ''}
        onChange={(e) =>
          navigate({ ...search, event: e.target.value, room: undefined, lesson: undefined })
        }
      >
        {catalog.data?.events.map((e) => (
          <option key={e.eventId} value={e.eventId}>
            {e.name}
          </option>
        ))}
      </select>
      <select
        aria-label="Аудитория"
        className="h-11 max-w-40 rounded-md border bg-background px-2 text-sm"
        value={room?.roomId ?? ''}
        onChange={(e) =>
          navigate({
            ...search,
            event: event?.eventId,
            room: e.target.value,
            lesson: undefined,
          })
        }
      >
        <option value="">Выберите аудиторию</option>
        {event?.rooms.map((r) => (
          <option key={r.roomId} value={r.roomId}>
            {r.name} · {r.groupName}
          </option>
        ))}
      </select>
      {lessonPicker}
    </>
  )

  if (!allowed) return <PageStatePanel state="forbidden" />
  if (catalog.isPending) return <PageStatePanel state="loading" />
  if (catalog.error) return <PageStatePanel state="error" />
  return (
    <section
      className="flex h-[calc(100svh-2.5rem)] min-h-0 flex-col bg-background"
      aria-label={mode === 'school' ? 'Очное занятие' : 'Zoom-приём'}
    >
      <div className="relative flex shrink-0 flex-wrap items-center gap-1 border-b px-2 py-1">
        {mode === 'school' ? (
          <>
            <div className="hidden items-center gap-1 sm:flex">{schoolSettings}</div>
            <Button
              variant="ghost"
              className="min-h-11 min-w-0 max-w-36 flex-1 justify-between px-1 sm:hidden"
              aria-label="Настройки занятия"
              title={`${room?.name ?? 'Аудитория'} · Занятие ${lesson?.number ?? '—'}`}
              onClick={(event) => {
                event.currentTarget.focus()
                setSettingsOpen(true)
              }}
            >
              <span className="min-w-0 text-left">
                <span className="block truncate text-sm">{room?.name ?? 'Аудитория'}</span>
                <span className="block text-[11px] font-normal text-muted-foreground">
                  Занятие {lesson?.number ?? '—'}
                </span>
              </span>
              <ChevronDown className="size-3 shrink-0" />
            </Button>
          </>
        ) : (
          <>
            {student ? (
              <Button
                size="icon"
                variant="ghost"
                aria-label="Найти следующего школьника"
                onClick={() => setFindOpen(true)}
              >
                <Search />
              </Button>
            ) : null}
            {student ? (
              <div className="min-w-0 basis-[calc(100%-3rem)] pr-5 sm:flex-1 sm:basis-48">
                <div className="truncate text-sm font-semibold">{student.displayName}</div>
                <div className="truncate text-xs text-muted-foreground">
                  {[
                    student.grade ? `${student.grade} кл.` : null,
                    student.middleName,
                    student.groupName,
                  ]
                    .filter(Boolean)
                    .join(' · ')}
                </div>
              </div>
            ) : (
              <span className="px-1 font-semibold">Zoom-приём</span>
            )}
            {!student || (catalog.data?.courses.length ?? 0) > 1 ? (
              <select
                aria-label="Курс"
                className="h-11 max-w-40 rounded-md border bg-background px-2 text-sm"
                value={course?.courseId ?? ''}
                onChange={(e) => navigate({ course: e.target.value })}
              >
                {catalog.data?.courses.map((c) => (
                  <option key={c.courseId} value={c.courseId}>
                    {c.name}
                  </option>
                ))}
              </select>
            ) : null}
            {session ? (
              <Button variant="ghost" onClick={() => setVisitsOpen(true)}>
                За сессию · {new Set(visits.data?.visits.map((v) => v.studentId)).size}
              </Button>
            ) : null}
          </>
        )}
        {mode === 'zoom' ? lessonPicker : null}
        {boardEnabled ? (
          <Button
            variant="secondary"
            aria-pressed={mode === 'school' ? !!search.presentOnly : search.oralOnly !== false}
            onClick={() =>
              navigate(
                mode === 'school'
                  ? { ...search, presentOnly: !search.presentOnly }
                  : { ...search, oralOnly: search.oralOnly === false },
              )
            }
          >
            {mode === 'school'
              ? search.presentOnly
                ? 'Пришли'
                : 'Все'
              : search.oralOnly === false
                ? 'Все задачи'
                : 'Устные'}
          </Button>
        ) : null}
        <Button
          size="icon"
          variant="ghost"
          aria-label="Отменить последнее действие"
          title="Отменить · Ctrl/Cmd+Z"
          disabled={busy || (!undoTarget && !scopedPending.length) || !!board.data?.readOnly}
          onClick={undo}
        >
          <Undo2 />
        </Button>
        {mode === 'school' && room ? (
          <Button
            size="icon"
            variant="ghost"
            aria-label="Добавить в группу школьника"
            onClick={() => setFindOpen(true)}
          >
            <UserPlus />
          </Button>
        ) : null}
        <span
          className={
            mode === 'zoom' && !scopedPending.length && !isOffline
              ? 'absolute right-2 top-3 px-1 text-[11px] text-muted-foreground sm:static sm:ml-auto'
              : 'ml-auto px-1 text-[11px] text-muted-foreground'
          }
          role="status"
          title={compactStatus}
        >
          {!scopedPending.length && !isOffline ? (
            <>
              <Check className="size-4 sm:hidden" aria-hidden="true" />
              <span className="sr-only sm:not-sr-only">{compactStatus}</span>
            </>
          ) : (
            compactStatus
          )}
        </span>
      </div>
      {error || queueState.storageError || board.error || cells.error ? (
        <div
          className="flex flex-wrap items-center gap-2 border-b bg-destructive/10 p-2 text-sm text-destructive"
          role="alert"
        >
          {error ?? queueState.storageError ?? 'Не удалось загрузить таблицу.'}
          {error && undoTarget ? (
            <Button
              size="sm"
              variant="outline"
              onClick={() => {
                setSkippedUndo([...skippedUndo, undoTarget.operationId])
                setError(null)
              }}
            >
              Пропустить в undo
            </Button>
          ) : null}
          <Button
            size="sm"
            variant="ghost"
            onClick={() => {
              setError(null)
              void board.refetch()
              void cells.refetch()
            }}
          >
            Обновить
          </Button>
        </div>
      ) : null}
      {scopedPending
        .filter((e) => e.status === 'conflict' || e.status === 'failed')
        .map((entry) => (
          <div
            key={entry.id}
            className="flex flex-wrap items-center gap-2 border-b p-2 text-sm"
            role="alert"
          >
            <span>{entry.status === 'conflict' ? 'Ячейка уже изменена.' : entry.error}</span>
            {entry.command.kind === 'mark' ? (
              <span>
                Сейчас:{' '}
                {cellMap.get(liveCellKey(entry.command.studentId, entry.command.problemId))
                  ?.symbol || 'пусто'}{' '}
                · Ваше: {entry.command.value === 'plus' ? '+' : '−'}
              </span>
            ) : null}
            <Button size="sm" variant="outline" onClick={() => queue.discard(entry.id)}>
              Принять актуальное
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => {
                const command = entry.command
                const currentVersion =
                  command.kind === 'mark'
                    ? (cellMap.get(liveCellKey(command.studentId, command.problemId))?.version ?? 0)
                    : command.kind === 'attendance'
                      ? board.data?.students.find((s) => s.studentId === command.studentId)
                          ?.attendanceVersion
                      : undefined
                queue.retry(entry.id, currentVersion)
              }}
            >
              Применить моё
            </Button>
          </div>
        ))}
      {mode === 'school' && !room ? (
        <div className="grid gap-2 overflow-auto p-3 sm:grid-cols-2">
          {event?.rooms.map((r) => (
            <Button
              key={r.roomId}
              className="h-16 justify-start"
              variant="outline"
              onClick={() => navigate({ ...search, event: event.eventId, room: r.roomId })}
            >
              {r.name} · {r.groupName}
            </Button>
          ))}
          {!event ? <p>Пока нет очных событий с подтверждёнными аудиториями.</p> : null}
        </div>
      ) : null}
      {mode === 'zoom' && !student ? (
        <div className="mx-auto flex min-h-0 w-full max-w-2xl flex-1 flex-col p-3">
          <StudentSearch
            students={directory.data?.students ?? []}
            onSelect={openStudent}
            transfer={false}
          />
        </div>
      ) : null}
      {boardEnabled && (board.isPending || cells.isPending) ? (
        <PageStatePanel state="loading" />
      ) : null}
      {filterBoard && mode === 'school' ? (
        <LiveSchoolGrid
          board={filterBoard}
          expanded={expanded}
          onExpand={(id) => {
            void queue.flush()
            setExpanded(expanded === id ? null : id)
          }}
          display={display}
          onMark={mark}
          onAttendance={attend}
          attendance={attendance}
        />
      ) : null}
      {filterBoard && mode === 'zoom' ? (
        <>
          <LiveZoomGrid
            board={filterBoard}
            display={display}
            onMark={mark}
            onCondition={setConditionProblem}
          />
          <div className="shrink-0 border-t bg-background px-2 py-1 sm:flex sm:items-center sm:gap-2">
            <div className="flex gap-1 overflow-x-auto" aria-label="Внутренние пометки">
              {LIVE_REACTIONS.map((reaction) => (
                <Button
                  key={reaction.id}
                  size="sm"
                  className="min-h-11 shrink-0"
                  variant={
                    board.data?.visit?.reactions.includes(reaction.id) ? 'secondary' : 'ghost'
                  }
                  aria-pressed={!!board.data?.visit?.reactions.includes(reaction.id)}
                  title={`${reaction.label} · видно только сотрудникам`}
                  disabled={busy || !!board.data?.readOnly}
                  onClick={() => {
                    if (spec && student)
                      void action(async () => {
                        await queue.flush()
                        const current = await client.visit(spec)
                        const values = current.reactions.includes(reaction.id)
                          ? current.reactions.filter((id) => id !== reaction.id)
                          : [...current.reactions, reaction.id]
                        await execute({
                          kind: 'reaction',
                          operationId: crypto.randomUUID(),
                          context: spec,
                          studentId: student.studentId,
                          expectedVersion: current.version,
                          reactions: values as (300 | 301 | 303 | 304 | 305)[],
                        })
                      })
                  }}
                >
                  {reaction.short}
                </Button>
              ))}
            </div>
            <div className="flex items-center gap-1 sm:flex-1">
              <Button
                size="sm"
                className="min-h-11"
                variant="outline"
                disabled={busy || !!board.data?.readOnly || !!board.data?.visit?.praisedAt}
                onClick={() => {
                  if (spec && student)
                    void action(async () => {
                      await queue.flush()
                      const current = await client.visit(spec)
                      await execute({
                        kind: 'praise',
                        operationId: crypto.randomUUID(),
                        context: spec,
                        studentId: student.studentId,
                        expectedVersion: current.version,
                      })
                    })
                }}
              >
                {board.data?.visit?.praisedAt ? (
                  <>
                    <Check /> Похвала отправлена
                  </>
                ) : (
                  'Похвалить ученика'
                )}
              </Button>
              <Button
                className="ml-auto min-h-11"
                size="sm"
                onClick={() => {
                  void queue.flush()
                  setFindOpen(true)
                }}
              >
                Следующий
              </Button>
            </div>
          </div>
        </>
      ) : null}
      {conditionProblem && spec ? (
        <LiveConditionDialog
          client={client}
          accountId={accountId}
          context={spec}
          problem={conditionProblem}
          onClose={() => setConditionProblem(null)}
        />
      ) : null}
      <Dialog open={settingsOpen} onOpenChange={setSettingsOpen}>
        <DialogContent className="max-h-[85svh] overflow-auto">
          <DialogHeader>
            <DialogTitle>Настройки занятия</DialogTitle>
            <DialogDescription>Событие, аудитория и список задач</DialogDescription>
          </DialogHeader>
          <div className="flex flex-col gap-3 [&_select]:w-full [&_select]:max-w-full">
            {schoolSettings}
          </div>
          <Button onClick={() => setSettingsOpen(false)}>Готово</Button>
        </DialogContent>
      </Dialog>
      <Dialog
        open={findOpen}
        onOpenChange={(open) => {
          setFindOpen(open)
          if (!open) setTransferStudent(null)
        }}
      >
        <DialogContent className="flex max-h-[85svh] flex-col sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>
              {mode === 'school' ? 'Добавить в группу школьника' : 'Следующий школьник'}
            </DialogTitle>
            <DialogDescription>
              {mode === 'school'
                ? `Перенос в аудиторию ${room?.name ?? ''}`
                : 'Поиск по всему курсу'}
            </DialogDescription>
          </DialogHeader>
          {transferStudent ? (
            <div className="space-y-3">
              <p className="font-semibold">
                {transferStudent.displayName} {transferStudent.middleName}
              </p>
              <p className="text-sm">
                {transferStudent.attendanceMode === 'online' ? 'Онлайн → очно' : 'Очно'} ·{' '}
                {transferStudent.groupName} → {room?.groupName} · аудитория {room?.name}. Посещение:
                пришёл.
              </p>
              <p className="text-xs text-muted-foreground">
                Режим и уровень меняются постоянно. Перенос можно отменить.
              </p>
              <div className="flex gap-2">
                <Button variant="ghost" onClick={() => setTransferStudent(null)}>
                  <ArrowLeft /> Назад
                </Button>
                <Button
                  disabled={busy || !navigator.onLine || !board.data?.planId}
                  onClick={() => {
                    if (spec && board.data?.planId)
                      void action(async () => {
                        await execute({
                          kind: 'transfer',
                          operationId: crypto.randomUUID(),
                          context: spec,
                          studentId: transferStudent.studentId,
                          enrollmentVersion: transferStudent.enrollmentVersion,
                          planId: board.data.planId!,
                        })
                        setTransferStudent(null)
                        setFindOpen(false)
                      })
                  }}
                >
                  Перенести в {room?.name}
                </Button>
              </div>
            </div>
          ) : (
            <StudentSearch
              students={directory.data?.students ?? []}
              transfer={mode === 'school'}
              onSelect={mode === 'school' ? setTransferStudent : openStudent}
            />
          )}
        </DialogContent>
      </Dialog>
      <Dialog open={visitsOpen} onOpenChange={setVisitsOpen}>
        <DialogContent className="flex max-h-[85svh] flex-col">
          <DialogHeader>
            <DialogTitle>Школьники за сессию</DialogTitle>
            <DialogDescription>
              {session?.finishedAt
                ? 'Завершённая сессия · только просмотр'
                : 'Можно вернуться и исправить оценки'}
            </DialogDescription>
          </DialogHeader>
          <select
            aria-label="Сессия"
            value={session?.sessionId ?? ''}
            className="h-11 rounded border bg-background p-2 text-sm"
            onChange={(e) =>
              navigate({
                ...search,
                session: e.target.value,
                student: undefined,
                lesson: undefined,
              })
            }
          >
            {course?.sessions.map((s) => (
              <option key={s.sessionId} value={s.sessionId}>
                {new Date(s.createdAt).toLocaleString('ru-RU')}{' '}
                {s.finishedAt ? '· завершена' : '· активна'}
              </option>
            ))}
          </select>
          <div className="min-h-0 overflow-auto">
            {visits.data?.visits.map((v) => (
              <button
                key={`${v.studentId}:${v.lessonId}`}
                type="button"
                className="flex min-h-12 w-full items-center justify-between gap-2 border-b p-2 text-left hover:bg-accent"
                onClick={() => {
                  navigate({
                    ...search,
                    session: session?.sessionId,
                    student: v.studentId,
                    lesson: v.lessonId,
                  })
                  setVisitsOpen(false)
                }}
              >
                <span>{v.displayName}</span>
                <span className="text-xs text-muted-foreground">
                  {v.changedCount} оценок ·{' '}
                  {new Date(v.updatedAt).toLocaleTimeString('ru-RU', {
                    hour: '2-digit',
                    minute: '2-digit',
                  })}
                </span>
              </button>
            ))}
          </div>
          {session?.finishedAt ? (
            <Button
              onClick={() => {
                void action(async () => {
                  const next = await client.start(course!.courseId)
                  await catalog.refetch()
                  navigate({ course: course!.courseId, session: next.sessionId })
                  setVisitsOpen(false)
                })
              }}
            >
              Новая сессия
            </Button>
          ) : (
            <Button
              variant="outline"
              disabled={busy}
              onClick={() => {
                if (session)
                  void action(async () => {
                    await queue.flush()
                    if (
                      queue
                        .getSnapshot()
                        .entries.some((e) => e.command.context.contextId === session.sessionId)
                    ) {
                      setError('Сначала отправьте или разрешите все изменения этой сессии.')
                      return
                    }
                    await client.finish(session.sessionId)
                    await board.refetch()
                    await catalog.refetch()
                    setVisitsOpen(false)
                    navigate({ ...search, session: session.sessionId })
                  })
              }}
            >
              <X /> Завершить сессию
            </Button>
          )}
        </DialogContent>
      </Dialog>
    </section>
  )
}
