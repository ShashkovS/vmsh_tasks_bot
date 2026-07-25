import {
  Archive,
  Bell,
  Building2,
  Check,
  CircleAlert,
  History,
  Pencil,
  Plus,
  RefreshCw,
  RotateCcw,
  Search,
  TriangleAlert,
  UsersRound,
} from 'lucide-react'
import { useId, useMemo, useState } from 'react'

import {
  Alert,
  AlertContent,
  AlertDescription,
  AlertTitle,
  Badge,
  Button,
  Input,
  Label,
  cn,
} from '@vmsh/ui'

const selectClass =
  'min-h-(--touch-target) rounded-md border border-input bg-surface px-2 text-small text-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/40'

export interface ClassroomGroupOption {
  id: string
  name: string
  shortCode: string
}

/* ── Catalog ────────────────────────────────────────────────────────────── */

export type ClassroomCatalogStatus = 'active' | 'archived'
export type ClassroomCatalogFilter = ClassroomCatalogStatus | 'all'

export interface ClassroomCatalogRoom {
  id: string
  name: string
  status: ClassroomCatalogStatus
  version: number
  usageLabel?: string
}

export interface ClassroomNameConflict {
  inputName: string
  existingRoomId: string
  existingRoomName: string
}

export interface ClassroomCatalogProps {
  rooms: ClassroomCatalogRoom[]
  query: string
  statusFilter: ClassroomCatalogFilter
  newRoomName: string
  conflict?: ClassroomNameConflict | null
  pendingRoomId?: string | null
  onQueryChange?: (value: string) => void
  onStatusFilterChange?: (value: ClassroomCatalogFilter) => void
  onNewRoomNameChange?: (value: string) => void
  onCreate?: (name: string) => void
  onRename?: (roomId: string, name: string) => void
  onArchive?: (roomId: string) => void
  onRestore?: (roomId: string) => void
  onRevealConflict?: (roomId: string) => void
  className?: string
}

function includesRoomQuery(room: ClassroomCatalogRoom, query: string) {
  return room.name.toLocaleLowerCase('ru').includes(query.trim().toLocaleLowerCase('ru'))
}

export function ClassroomCatalog({
  rooms,
  query,
  statusFilter,
  newRoomName,
  conflict,
  pendingRoomId,
  onQueryChange,
  onStatusFilterChange,
  onNewRoomNameChange,
  onCreate,
  onRename,
  onArchive,
  onRestore,
  onRevealConflict,
  className,
}: ClassroomCatalogProps) {
  const searchId = useId()
  const statusId = useId()
  const newRoomId = useId()
  const [editing, setEditing] = useState<{ id: string; name: string } | null>(null)

  const visibleRooms = useMemo(
    () =>
      rooms.filter(
        (room) =>
          (statusFilter === 'all' || room.status === statusFilter) &&
          includesRoomQuery(room, query),
      ),
    [query, rooms, statusFilter],
  )
  const activeCount = rooms.filter((room) => room.status === 'active').length
  const archivedCount = rooms.length - activeCount
  const trimmedNewName = newRoomName.trim()

  return (
    <section className={cn('space-y-4', className)} data-density="staff">
      <header className="space-y-1">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h2 className="text-title font-semibold text-foreground">Каталог аудиторий</h2>
            <p className="text-small text-muted-foreground">
              Один список для всех занятий. Скрытые аудитории можно восстановить.
            </p>
          </div>
          <div className="flex gap-1.5" aria-label="Сводка каталога">
            <Badge variant="neutral">Активных: {activeCount}</Badge>
            <Badge variant="outline">Скрытых: {archivedCount}</Badge>
          </div>
        </div>
      </header>

      <form
        className="grid gap-2 rounded-md border border-border bg-surface-subtle p-3 sm:grid-cols-[minmax(0,1fr)_auto]"
        onSubmit={(event) => {
          event.preventDefault()
          if (trimmedNewName) onCreate?.(trimmedNewName)
        }}
      >
        <div className="space-y-1">
          <Label htmlFor={newRoomId}>Новая аудитория</Label>
          <Input
            aria-describedby={`${newRoomId}-hint`}
            aria-invalid={conflict ? true : undefined}
            id={newRoomId}
            onChange={(event) => onNewRoomNameChange?.(event.target.value)}
            placeholder="Например, 201 или Актовый зал"
            value={newRoomName}
          />
          <p className="text-caption text-muted-foreground" id={`${newRoomId}-hint`}>
            Пробелы по краям уберутся; регистр не создаёт новую аудиторию.
          </p>
        </div>
        <Button className="self-end" disabled={!trimmedNewName} size="sm" type="submit">
          <Plus aria-hidden="true" />
          Добавить
        </Button>
      </form>

      {conflict ? (
        <Alert role="alert" tone="danger">
          <CircleAlert aria-hidden="true" />
          <AlertContent>
            <AlertTitle>Такая аудитория уже есть</AlertTitle>
            <AlertDescription>
              «{conflict.inputName.trim()}» совпадает с «{conflict.existingRoomName}» без учёта
              регистра и формы Unicode.
            </AlertDescription>
            <Button
              className="mt-2"
              onClick={() => onRevealConflict?.(conflict.existingRoomId)}
              size="xs"
              variant="outline"
            >
              Показать существующую
            </Button>
          </AlertContent>
        </Alert>
      ) : null}

      <div className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_12rem]">
        <div className="space-y-1">
          <Label htmlFor={searchId}>Поиск</Label>
          <div className="relative">
            <Search
              aria-hidden="true"
              className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground"
            />
            <Input
              className="pl-8"
              id={searchId}
              onChange={(event) => onQueryChange?.(event.target.value)}
              placeholder="Название аудитории"
              value={query}
            />
          </div>
        </div>
        <div className="space-y-1">
          <Label htmlFor={statusId}>Показывать</Label>
          <select
            className={cn(selectClass, 'w-full')}
            id={statusId}
            onChange={(event) =>
              onStatusFilterChange?.(event.target.value as ClassroomCatalogFilter)
            }
            value={statusFilter}
          >
            <option value="active">Активные</option>
            <option value="archived">Скрытые</option>
            <option value="all">Все</option>
          </select>
        </div>
      </div>

      {visibleRooms.length > 0 ? (
        <ul className="divide-y divide-border rounded-md border border-border bg-surface">
          {visibleRooms.map((room) => {
            const isEditing = editing?.id === room.id
            const pending = pendingRoomId === room.id
            return (
              <li
                className="grid gap-2 p-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center"
                data-room-id={room.id}
                key={room.id}
              >
                {isEditing ? (
                  <div className="flex min-w-0 gap-2">
                    <Input
                      aria-label={`Новое название: ${room.name}`}
                      onChange={(event) => setEditing({ id: room.id, name: event.target.value })}
                      value={editing.name}
                    />
                    <Button
                      disabled={!editing.name.trim()}
                      onClick={() => {
                        onRename?.(room.id, editing.name.trim())
                        setEditing(null)
                      }}
                      size="xs"
                    >
                      Сохранить
                    </Button>
                    <Button onClick={() => setEditing(null)} size="xs" variant="ghost">
                      Отмена
                    </Button>
                  </div>
                ) : (
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-medium text-foreground">{room.name}</span>
                      <Badge variant={room.status === 'active' ? 'success' : 'neutral'}>
                        {room.status === 'active' ? 'Активна' : 'Скрыта'}
                      </Badge>
                    </div>
                    <p className="text-caption text-muted-foreground">
                      {room.usageLabel ?? `Версия ${room.version}`}
                    </p>
                  </div>
                )}

                {!isEditing ? (
                  <div className="flex flex-wrap gap-1 sm:justify-end">
                    <Button
                      aria-label={`Переименовать: ${room.name}`}
                      disabled={pending}
                      onClick={() => setEditing({ id: room.id, name: room.name })}
                      size="xs"
                      variant="ghost"
                    >
                      <Pencil aria-hidden="true" />
                      Переименовать
                    </Button>
                    {room.status === 'active' ? (
                      <Button
                        disabled={pending}
                        onClick={() => onArchive?.(room.id)}
                        size="xs"
                        variant="outline"
                      >
                        <Archive aria-hidden="true" />
                        Скрыть
                      </Button>
                    ) : (
                      <Button
                        disabled={pending}
                        onClick={() => onRestore?.(room.id)}
                        size="xs"
                        variant="outline"
                      >
                        <RotateCcw aria-hidden="true" />
                        Восстановить
                      </Button>
                    )}
                  </div>
                ) : null}
              </li>
            )
          })}
        </ul>
      ) : (
        <div className="rounded-md border border-dashed border-border p-6 text-center">
          <Building2 aria-hidden="true" className="mx-auto mb-2 size-6 text-muted-foreground" />
          <p className="text-small font-medium text-foreground">Аудитории не найдены</p>
          <p className="text-caption text-muted-foreground">
            Измените поиск или фильтр. Данные каталога не удалены.
          </p>
        </div>
      )}
    </section>
  )
}

/* ── Effective room-to-group layout ────────────────────────────────────── */

export type ClassroomLayoutState = 'inherited' | 'draft' | 'confirmed'

export interface ClassroomLayoutRoom {
  id: string
  name: string
  groupId: string | null
  invalid?: boolean
}

export interface ClassroomGroupLayoutProps {
  lessonLabel: string
  state: ClassroomLayoutState
  rooms: ClassroomLayoutRoom[]
  groups: ClassroomGroupOption[]
  sourceLabel?: string
  version: number
  optimisticConflict?: string | null
  pending?: boolean
  onMaterialize?: () => void
  onRoomGroupChange?: (roomId: string, groupId: string | null) => void
  onConfirm?: () => void
  className?: string
}

export function ClassroomGroupLayout({
  lessonLabel,
  state,
  rooms,
  groups,
  sourceLabel,
  version,
  optimisticConflict,
  pending,
  onMaterialize,
  onRoomGroupChange,
  onConfirm,
  className,
}: ClassroomGroupLayoutProps) {
  const editable = state === 'draft'
  const invalidRooms = rooms.filter((room) => room.invalid)
  const unassignedCount = rooms.filter((room) => room.groupId === null).length

  return (
    <section className={cn('space-y-4', className)} data-density="staff">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-title font-semibold text-foreground">Аудитории по группам</h2>
            <Badge
              variant={state === 'draft' ? 'warning' : state === 'confirmed' ? 'success' : 'info'}
            >
              {state === 'draft'
                ? 'Черновик'
                : state === 'confirmed'
                  ? 'Подтверждено'
                  : 'Унаследовано'}
            </Badge>
          </div>
          <p className="text-small text-muted-foreground">
            {lessonLabel} · версия {version}
            {sourceLabel ? ` · ${sourceLabel}` : ''}
          </p>
        </div>
        {state === 'inherited' ? (
          <Button onClick={onMaterialize} size="sm" variant="outline">
            <Pencil aria-hidden="true" />
            Изменить для занятия
          </Button>
        ) : null}
      </header>

      {state === 'inherited' ? (
        <Alert tone="info">
          <History aria-hidden="true" />
          <AlertContent>
            <AlertTitle>Используется последняя подтверждённая схема</AlertTitle>
            <AlertDescription>
              Пока вы ничего не меняете, отдельная копия для этого занятия не создаётся.
            </AlertDescription>
          </AlertContent>
        </Alert>
      ) : null}

      {optimisticConflict ? (
        <Alert role="alert" tone="danger">
          <RefreshCw aria-hidden="true" />
          <AlertContent>
            <AlertTitle>Схема уже изменилась</AlertTitle>
            <AlertDescription>{optimisticConflict}</AlertDescription>
          </AlertContent>
        </Alert>
      ) : null}

      {invalidRooms.length > 0 ? (
        <Alert role="alert" tone="danger">
          <TriangleAlert aria-hidden="true" />
          <AlertContent>
            <AlertTitle>Есть скрытая аудитория</AlertTitle>
            <AlertDescription>
              Уберите {invalidRooms.map((room) => room.name).join(', ')} из схемы перед
              подтверждением.
            </AlertDescription>
          </AlertContent>
        </Alert>
      ) : null}

      <div
        className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4"
        aria-label="Число аудиторий по группам"
      >
        {groups.map((group) => {
          const count = rooms.filter((room) => room.groupId === group.id).length
          return (
            <div className="rounded-md border border-border bg-surface-subtle p-3" key={group.id}>
              <p className="text-caption text-muted-foreground">{group.name}</p>
              <p className="font-num text-title font-semibold text-foreground">{count}</p>
              <p className="text-caption text-muted-foreground">аудиторий</p>
            </div>
          )
        })}
        <div className="rounded-md border border-dashed border-border p-3">
          <p className="text-caption text-muted-foreground">Не используются</p>
          <p className="font-num text-title font-semibold text-foreground">{unassignedCount}</p>
          <p className="text-caption text-muted-foreground">аудиторий</p>
        </div>
      </div>

      <div className="overflow-hidden rounded-md border border-border bg-surface">
        <ul className="divide-y divide-border">
          {rooms.map((room) => (
            <li
              className={cn(
                'grid gap-2 p-3 sm:grid-cols-[minmax(0,1fr)_minmax(12rem,18rem)] sm:items-center',
                room.invalid && 'bg-status-danger-surface',
              )}
              key={room.id}
            >
              <div>
                <p className="font-medium text-foreground">{room.name}</p>
                {room.invalid ? (
                  <p className="text-caption text-status-danger">Аудитория скрыта в каталоге</p>
                ) : null}
              </div>
              <select
                aria-label={`Группа для аудитории ${room.name}`}
                className={cn(selectClass, 'w-full')}
                disabled={!editable || pending}
                onChange={(event) =>
                  onRoomGroupChange?.(
                    room.id,
                    event.target.value === '' ? null : event.target.value,
                  )
                }
                value={room.groupId ?? ''}
              >
                <option value="">Не используется</option>
                {groups.map((group) => (
                  <option key={group.id} value={group.id}>
                    {group.name}
                  </option>
                ))}
              </select>
            </li>
          ))}
        </ul>
      </div>

      {editable ? (
        <div className="flex flex-wrap items-center justify-between gap-2 border-t border-border pt-3">
          <p className="text-caption text-muted-foreground">
            Неиспользованные активные аудитории не мешают подтверждению.
          </p>
          <Button disabled={pending || invalidRooms.length > 0} onClick={onConfirm} size="sm">
            <Check aria-hidden="true" />
            Подтвердить схему
          </Button>
        </div>
      ) : null}
    </section>
  )
}

/* ── Per-lesson student assignment plan ────────────────────────────────── */

export type ClassroomPlanState = 'draft' | 'confirmed' | 'stale'
export type ClassroomStudentStatus = 'assigned' | 'reassigning' | 'unassigned'
export type ClassroomAssignmentSource =
  'previous-room' | 'least-loaded' | 'manual' | 'group-change' | 'mode-change' | 'import'

export interface ClassroomPlanRoom {
  id: string
  name: string
  groupId: string
}

export interface ClassroomPlanStudent {
  id: string
  name: string
  groupId: string
  classroomId: string | null
  status: ClassroomStudentStatus
  source: ClassroomAssignmentSource
}

export interface ClassroomPlanIncident {
  id: string
  title: string
  description: string
  blocking: boolean
}

export interface ClassroomStudentPlannerProps {
  lessonLabel: string
  state: ClassroomPlanState
  version: number
  groups: ClassroomGroupOption[]
  rooms: ClassroomPlanRoom[]
  students: ClassroomPlanStudent[]
  incidents?: ClassroomPlanIncident[]
  staleReason?: string
  publishedAt?: string
  pending?: boolean
  onMove?: (studentId: string, classroomId: string) => void
  onRecalculate?: () => void
  onConfirm?: () => void
  className?: string
}

const sourceLabels: Record<ClassroomAssignmentSource, string> = {
  'previous-room': 'прежняя аудитория',
  'least-loaded': 'по фактической загрузке',
  manual: 'вручную',
  'group-change': 'после смены группы',
  'mode-change': 'после смены режима',
  import: 'импорт',
}

function StudentMoveSelect({
  student,
  rooms,
  pending,
  onMove,
}: {
  student: ClassroomPlanStudent
  rooms: ClassroomPlanRoom[]
  pending?: boolean | undefined
  onMove?: ((studentId: string, classroomId: string) => void) | undefined
}) {
  const eligibleRooms = rooms.filter((room) => room.groupId === student.groupId)
  return (
    <select
      aria-label={`Аудитория для ${student.name}`}
      className={cn(selectClass, 'w-full min-w-36')}
      disabled={pending || eligibleRooms.length === 0}
      onChange={(event) => {
        if (event.target.value) onMove?.(student.id, event.target.value)
      }}
      value={student.classroomId ?? ''}
    >
      <option value="">Не назначена</option>
      {eligibleRooms.map((room) => (
        <option key={room.id} value={room.id}>
          {room.name}
        </option>
      ))}
    </select>
  )
}

export function ClassroomStudentPlanner({
  lessonLabel,
  state,
  version,
  groups,
  rooms,
  students,
  incidents = [],
  staleReason,
  publishedAt,
  pending,
  onMove,
  onRecalculate,
  onConfirm,
  className,
}: ClassroomStudentPlannerProps) {
  const unresolved = students.filter((student) => student.status !== 'assigned')
  const blocking = incidents.some((incident) => incident.blocking) || unresolved.length > 0
  const assignedCount = students.length - unresolved.length

  return (
    <section className={cn('space-y-4', className)} data-density="staff">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-title font-semibold text-foreground">Школьники по аудиториям</h2>
            <Badge
              variant={state === 'confirmed' ? 'success' : state === 'stale' ? 'danger' : 'warning'}
            >
              {state === 'confirmed'
                ? 'Подтверждено'
                : state === 'stale'
                  ? 'Нужно пересчитать'
                  : 'Предпросмотр'}
            </Badge>
          </div>
          <p className="text-small text-muted-foreground">
            {lessonLabel} · версия {version}
            {publishedAt ? ` · опубликовано ${publishedAt}` : ''}
          </p>
        </div>
        <div className="flex gap-1.5" aria-label="Сводка плана">
          <Badge variant="neutral">Назначено: {assignedCount}</Badge>
          {unresolved.length > 0 ? (
            <Badge variant="danger">Требуют внимания: {unresolved.length}</Badge>
          ) : null}
        </div>
      </header>

      {state === 'stale' ? (
        <Alert role="alert" tone="danger">
          <RefreshCw aria-hidden="true" />
          <AlertContent>
            <AlertTitle>План устарел</AlertTitle>
            <AlertDescription>
              {staleReason ?? 'Схема аудиторий изменилась. Проверьте новый предпросмотр.'}
            </AlertDescription>
          </AlertContent>
        </Alert>
      ) : null}

      {incidents.map((incident) => (
        <Alert
          key={incident.id}
          role={incident.blocking ? 'alert' : 'status'}
          tone={incident.blocking ? 'danger' : 'warning'}
        >
          <TriangleAlert aria-hidden="true" />
          <AlertContent>
            <AlertTitle>{incident.title}</AlertTitle>
            <AlertDescription>{incident.description}</AlertDescription>
          </AlertContent>
        </Alert>
      ))}

      <div className="space-y-4">
        {groups.map((group) => {
          const groupRooms = rooms.filter((room) => room.groupId === group.id)
          const groupStudents = students.filter((student) => student.groupId === group.id)
          const unresolvedGroup = groupStudents.filter((student) => student.status !== 'assigned')
          return (
            <section
              aria-labelledby={`classroom-group-${group.id}`}
              className="space-y-3 rounded-md border border-border bg-surface-subtle p-3"
              key={group.id}
            >
              <header className="flex flex-wrap items-baseline justify-between gap-2">
                <div>
                  <h3
                    className="text-label font-semibold text-foreground"
                    id={`classroom-group-${group.id}`}
                  >
                    {group.name}
                  </h3>
                  <p className="text-caption text-muted-foreground">
                    {groupRooms.length} аудиторий · {groupStudents.length} школьников
                  </p>
                </div>
                {groupStudents.length === 0 ? <Badge variant="neutral">Группа пуста</Badge> : null}
              </header>

              {groupRooms.length > 0 ? (
                <div className="grid gap-2 lg:grid-cols-2 2xl:grid-cols-3">
                  {groupRooms.map((room) => {
                    const roomStudents = groupStudents.filter(
                      (student) => student.classroomId === room.id && student.status === 'assigned',
                    )
                    return (
                      <section
                        aria-label={`Аудитория ${room.name}`}
                        className="rounded-md border border-border bg-surface p-3"
                        key={room.id}
                      >
                        <div className="mb-2 flex items-baseline justify-between gap-2">
                          <h4 className="font-medium text-foreground">{room.name}</h4>
                          <span className="font-num text-caption text-muted-foreground">
                            {roomStudents.length} школьников
                          </span>
                        </div>
                        {roomStudents.length > 0 ? (
                          <ul className="space-y-2">
                            {roomStudents.map((student) => (
                              <li
                                className="grid gap-1 text-small sm:grid-cols-[minmax(0,1fr)_minmax(9rem,12rem)] sm:items-center"
                                key={student.id}
                              >
                                <div className="min-w-0">
                                  <p className="truncate text-foreground">{student.name}</p>
                                  <p className="text-caption text-muted-foreground">
                                    {sourceLabels[student.source]}
                                  </p>
                                </div>
                                <StudentMoveSelect
                                  onMove={onMove}
                                  pending={pending}
                                  rooms={rooms}
                                  student={student}
                                />
                              </li>
                            ))}
                          </ul>
                        ) : (
                          <p className="text-caption text-muted-foreground">Пока никого нет</p>
                        )}
                      </section>
                    )
                  })}
                </div>
              ) : (
                <Alert role="alert" tone={groupStudents.length > 0 ? 'danger' : 'neutral'}>
                  <Building2 aria-hidden="true" />
                  <AlertContent>
                    <AlertTitle>У группы нет аудитории</AlertTitle>
                    <AlertDescription>
                      {groupStudents.length > 0
                        ? 'Назначьте группе хотя бы одну активную аудиторию.'
                        : 'Это допустимо, пока в группе нет очных школьников.'}
                    </AlertDescription>
                  </AlertContent>
                </Alert>
              )}

              {unresolvedGroup.length > 0 ? (
                <div className="space-y-2 rounded-md border border-status-danger-border bg-status-danger-surface p-3">
                  <p className="text-label font-medium text-foreground">
                    Аудитория переназначается
                  </p>
                  <ul className="space-y-2">
                    {unresolvedGroup.map((student) => (
                      <li
                        className="grid gap-1 text-small sm:grid-cols-[minmax(0,1fr)_minmax(9rem,12rem)] sm:items-center"
                        key={student.id}
                      >
                        <div>
                          <p className="text-foreground">{student.name}</p>
                          <p className="text-caption text-muted-foreground">
                            {student.status === 'reassigning'
                              ? 'Прежнее назначение сброшено'
                              : 'Ещё не назначена'}
                          </p>
                        </div>
                        <StudentMoveSelect
                          onMove={onMove}
                          pending={pending}
                          rooms={rooms}
                          student={student}
                        />
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
            </section>
          )
        })}
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2 border-t border-border pt-3">
        <p className="text-caption text-muted-foreground">
          Пересчёт сначала сохраняет прежнюю допустимую аудиторию, затем использует фактическое
          число школьников.
        </p>
        <div className="flex gap-2">
          <Button disabled={pending} onClick={onRecalculate} size="sm" variant="outline">
            <RefreshCw aria-hidden="true" />
            Пересчитать
          </Button>
          <Button
            disabled={pending || blocking || state === 'confirmed' || state === 'stale'}
            onClick={onConfirm}
            size="sm"
          >
            <Check aria-hidden="true" />
            Подтвердить план
          </Button>
        </div>
      </div>
    </section>
  )
}

/* ── Student / Family published assignment ─────────────────────────────── */

export type ClassroomAssignmentPublicStatus = 'not_applicable' | 'reassigning' | 'assigned'

export interface ClassroomAssignmentStatusProps {
  audience: 'student' | 'family'
  status: ClassroomAssignmentPublicStatus
  classroomName?: string
  publishedAt?: string
  studentName?: string
  onOpenNotificationSettings?: () => void
  className?: string
}

export function ClassroomAssignmentStatus({
  audience,
  status,
  classroomName,
  publishedAt,
  studentName,
  onOpenNotificationSettings,
  className,
}: ClassroomAssignmentStatusProps) {
  if (status === 'reassigning') {
    return (
      <Alert className={className} role="status" tone="warning">
        <RefreshCw aria-hidden="true" />
        <AlertContent>
          <AlertTitle>Аудитория переназначается</AlertTitle>
          <AlertDescription>
            {audience === 'student'
              ? 'Прежняя аудитория больше не действует. Новая появится здесь после подтверждения.'
              : 'Прежняя аудитория ребёнка больше не действует. Новая появится после подтверждения.'}
          </AlertDescription>
          {publishedAt ? (
            <p className="mt-1 text-caption text-muted-foreground">Обновлено {publishedAt}</p>
          ) : null}
          {audience === 'student' && onOpenNotificationSettings ? (
            <Button
              className="mt-2"
              onClick={onOpenNotificationSettings}
              size="xs"
              variant="outline"
            >
              <Bell aria-hidden="true" />
              Настроить уведомления
            </Button>
          ) : null}
        </AlertContent>
      </Alert>
    )
  }

  if (status === 'not_applicable') {
    return (
      <Alert className={className} tone="neutral">
        <UsersRound aria-hidden="true" />
        <AlertContent>
          <AlertTitle>Очная аудитория не требуется</AlertTitle>
          <AlertDescription>
            {audience === 'student'
              ? 'Сейчас у вас онлайн-режим.'
              : studentName
                ? `${studentName}: сейчас онлайн-режим.`
                : 'Сейчас у ребёнка онлайн-режим.'}
          </AlertDescription>
        </AlertContent>
      </Alert>
    )
  }

  return (
    <section
      aria-label={audience === 'student' ? 'Ваша аудитория' : 'Аудитория ребёнка'}
      className={cn('rounded-md border border-border bg-surface p-4', className)}
    >
      <div className="flex items-start gap-3">
        <div className="rounded-md bg-surface-sunken p-2 text-primary">
          <Building2 aria-hidden="true" className="size-5" />
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-caption text-muted-foreground">
            {audience === 'student' ? 'Ваша аудитория' : `Аудитория: ${studentName ?? 'ребёнок'}`}
          </p>
          <p className="text-title font-semibold text-foreground">
            {classroomName ?? 'Название уточняется'}
          </p>
          {publishedAt ? (
            <p className="mt-1 text-caption text-muted-foreground">Опубликовано {publishedAt}</p>
          ) : null}
        </div>
        <Badge variant="success">Назначена</Badge>
      </div>
      {audience === 'student' && onOpenNotificationSettings ? (
        <Button className="mt-3" onClick={onOpenNotificationSettings} size="xs" variant="ghost">
          <Bell aria-hidden="true" />
          Уведомления об изменениях
        </Button>
      ) : null}
    </section>
  )
}
