import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useMemo, useState } from 'react'

import {
  ClassroomNetworkError,
  PageStatePanel,
  createClassroomClient,
  useAuthenticatedPrincipal,
  useAuthentication,
} from '@vmsh/app-shell'
import { ApiResponseError, classroomQueryKeys, type ClassroomAssignmentPlan } from '@vmsh/contracts'
import {
  ClassroomStudentPlanner,
  type ClassroomGroupOption,
  type ClassroomPlanRoom,
  type ClassroomPlanStudent,
} from '@vmsh/product'
import { Alert, AlertContent, AlertDescription, AlertTitle, Button } from '@vmsh/ui'

function colorIndex(colorKey: string | null): 0 | 1 | 2 | 3 | 4 {
  const match = /^level-([1-4])$/.exec(colorKey ?? '')
  return match ? (Number(match[1]) as 1 | 2 | 3 | 4) : 0
}

function describeError(error: Error): string {
  if (error instanceof ApiResponseError) return error.message
  if (error instanceof ClassroomNetworkError) return 'Проверьте соединение и повторите попытку.'
  return 'Обновите страницу и повторите попытку.'
}

interface SavedAssignmentDraft {
  assignments: Record<string, string>
  groupChanges: string[]
}

function savedAssignments(storageKey: string): SavedAssignmentDraft | null {
  try {
    const raw = globalThis.localStorage.getItem(storageKey)
    if (raw === null) return null
    const parsed: unknown = JSON.parse(raw)
    if (typeof parsed !== 'object' || parsed === null || !('assignments' in parsed)) return null
    const value = (parsed as { assignments?: unknown }).assignments
    if (typeof value !== 'object' || value === null) return null
    const groupChanges =
      'groupChanges' in parsed && Array.isArray(parsed.groupChanges)
        ? parsed.groupChanges.filter((item): item is string => typeof item === 'string')
        : []
    return {
      assignments: Object.fromEntries(
        Object.entries(value).filter(
          (entry): entry is [string, string] => typeof entry[1] === 'string',
        ),
      ),
      groupChanges,
    }
  } catch {
    return null
  }
}

function serverAssignments(plan: ClassroomAssignmentPlan): Record<string, string> {
  return Object.fromEntries(
    plan.students.flatMap((student) =>
      student.classroomPublicId === null
        ? []
        : [[student.enrollmentPublicId, student.classroomPublicId]],
    ),
  )
}

function AssignmentEditor({
  eventPublicId,
  plan,
  storageKey,
  client,
  onChanged,
}: {
  eventPublicId: string
  plan: ClassroomAssignmentPlan
  storageKey: string
  client: ReturnType<typeof createClassroomClient>
  onChanged: () => Promise<void>
}) {
  const authentication = useAuthentication()
  const saved = useMemo(() => savedAssignments(storageKey), [storageKey])
  const [assignments, setAssignments] = useState(saved?.assignments ?? serverAssignments(plan))
  const [groupChanges, setGroupChanges] = useState<ReadonlySet<string>>(
    () => new Set(saved?.groupChanges ?? []),
  )
  const [storageFailed, setStorageFailed] = useState(false)
  const [groupChangeRequested, setGroupChangeRequested] = useState<{
    studentId: string
    groupId: string
    classroomId: string
  } | null>(null)
  const [historyStudentName, setHistoryStudentName] = useState<string | null>(null)

  const groups: ClassroomGroupOption[] = plan.groups.map((group) => ({
    id: group.groupLessonPublicId,
    courseId: group.coursePublicId,
    name: `${group.courseName} · ${group.groupName}`,
    shortCode: group.shortCode,
    colorIndex: colorIndex(group.colorKey),
    inPersonCount: group.inPersonCount,
    assignedCount: plan.students.filter(
      (student) =>
        student.groupLessonPublicId === group.groupLessonPublicId &&
        assignments[student.enrollmentPublicId] !== undefined,
    ).length,
  }))
  const rooms: ClassroomPlanRoom[] = plan.rooms
    .filter((room) => room.status === 'active')
    .map((room) => ({
      id: room.publicId,
      name: room.name,
      groupId: room.groupLessonPublicId,
    }))
  const students: ClassroomPlanStudent[] = plan.students.map((student) => {
    const classroomId = assignments[student.enrollmentPublicId]
    const selectedRoom = plan.rooms.find((room) => room.publicId === classroomId)
    const originalGroup = plan.groups.find(
      (group) => group.groupLessonPublicId === student.groupLessonPublicId,
    )
    return {
      id: student.enrollmentPublicId,
      name: `${student.surname} ${student.name}`,
      ...(originalGroup === undefined ? {} : { courseId: originalGroup.coursePublicId }),
      groupId:
        groupChanges.has(student.enrollmentPublicId) && selectedRoom
          ? selectedRoom.groupLessonPublicId
          : student.groupLessonPublicId,
      classroomId: classroomId ?? null,
      status: classroomId === undefined ? 'reassigning' : 'assigned',
      source: student.source,
      age: student.age,
      schoolClass: student.grade,
      strength: student.strength,
    }
  })
  const currentPlan = plan.plan

  const mutation = useMutation({
    mutationFn: async (kind: 'recalculate' | 'confirm') => {
      if (kind === 'recalculate') {
        return client.recalculateAssignmentPlan(
          eventPublicId,
          currentPlan === null || currentPlan.state === 'confirmed'
            ? null
            : { publicId: currentPlan.publicId, version: currentPlan.version },
          { schemaVersion: 1 },
        )
      }
      if (currentPlan === null || currentPlan.state !== 'draft') {
        throw new Error('Only a draft assignment plan can be confirmed')
      }
      const changed = plan.students.flatMap((student) => {
        const classroomPublicId = assignments[student.enrollmentPublicId]
        return classroomPublicId === undefined || classroomPublicId === student.classroomPublicId
          ? []
          : [
              {
                enrollmentPublicId: student.enrollmentPublicId,
                classroomPublicId,
                confirmGroupChange: groupChanges.has(student.enrollmentPublicId),
              },
            ]
      })
      const savedPlan =
        changed.length === 0
          ? plan
          : (
              await client.updateAssignmentPlan(
                eventPublicId,
                { publicId: currentPlan.publicId, version: currentPlan.version },
                { schemaVersion: 1, assignments: changed },
              )
            ).assignmentPlan
      if (savedPlan.plan === null) throw new Error('Server did not return the saved plan')
      return client.confirmAssignmentPlan(
        eventPublicId,
        { publicId: savedPlan.plan.publicId, version: savedPlan.plan.version },
        { schemaVersion: 1 },
      )
    },
    onSuccess: async (_result, kind) => {
      if (kind === 'confirm') {
        try {
          globalThis.localStorage.removeItem(storageKey)
        } catch {
          setStorageFailed(true)
        }
      }
      await onChanged()
    },
    onError: async (error) => {
      authentication.handleApiError(error)
      await onChanged()
    },
  })
  const historyMutation = useMutation({
    mutationFn: (enrollmentPublicId: string) => {
      if (currentPlan === null) throw new Error('Assignment plan is not available')
      return client.getAssignmentHistory(eventPublicId, currentPlan.publicId, enrollmentPublicId)
    },
    onError: (error) => authentication.handleApiError(error),
  })

  const saveDraft = (next: Record<string, string>, nextGroupChanges: ReadonlySet<string>) => {
    try {
      globalThis.localStorage.setItem(
        storageKey,
        JSON.stringify({ assignments: next, groupChanges: [...nextGroupChanges] }),
      )
      setStorageFailed(false)
    } catch {
      setStorageFailed(true)
    }
  }

  const move = (studentId: string, classroomId: string) => {
    const next = { ...assignments, [studentId]: classroomId }
    const nextGroupChanges = new Set(groupChanges)
    nextGroupChanges.delete(studentId)
    setAssignments(next)
    setGroupChanges(nextGroupChanges)
    saveDraft(next, nextGroupChanges)
  }

  const confirmGroupChange = () => {
    if (groupChangeRequested === null) return
    const next = {
      ...assignments,
      [groupChangeRequested.studentId]: groupChangeRequested.classroomId,
    }
    const nextGroupChanges = new Set(groupChanges).add(groupChangeRequested.studentId)
    setAssignments(next)
    setGroupChanges(nextGroupChanges)
    saveDraft(next, nextGroupChanges)
    setGroupChangeRequested(null)
  }
  const incidents = [
    ...(currentPlan === null
      ? [
          {
            id: 'not-calculated',
            title: 'План ещё не рассчитан',
            description: 'Сначала создайте предпросмотр распределения школьников.',
            blocking: true,
          },
        ]
      : []),
    ...(currentPlan?.state === 'confirmed' &&
    plan.students.some((student) => student.status === 'reassigning')
      ? [
          {
            id: 'confirmed-room-unavailable',
            title: 'Подтверждённая аудитория больше недоступна',
            description: 'Пересчитайте план и подтвердите новое распределение.',
            blocking: true,
          },
        ]
      : []),
  ]

  return (
    <div className="space-y-3">
      {storageFailed ? (
        <Alert role="alert" tone="danger">
          <AlertContent>
            <AlertTitle>Локальный черновик не сохранён</AlertTitle>
            <AlertDescription>Не закрывайте страницу до подтверждения плана.</AlertDescription>
          </AlertContent>
        </Alert>
      ) : null}
      {groupChangeRequested ? (
        <Alert role="status" tone="warning">
          <AlertContent>
            <AlertTitle>Сменить учебную группу школьника?</AlertTitle>
            <AlertDescription>
              Вместе с аудиторией изменится активная группа в этом курсе. Изменение попадёт в
              историю после подтверждения всего плана.
            </AlertDescription>
            <div className="mt-2 flex flex-wrap gap-2">
              <Button onClick={confirmGroupChange} size="sm" type="button" variant="outline">
                Сменить группу и аудиторию
              </Button>
              <Button
                onClick={() => setGroupChangeRequested(null)}
                size="sm"
                type="button"
                variant="ghost"
              >
                Отмена
              </Button>
            </div>
          </AlertContent>
        </Alert>
      ) : null}
      {mutation.error ? (
        <Alert role="alert" tone="danger">
          <AlertContent>
            <AlertTitle>План не сохранён</AlertTitle>
            <AlertDescription>{describeError(mutation.error)}</AlertDescription>
          </AlertContent>
        </Alert>
      ) : null}
      {historyStudentName ? (
        <section className="space-y-2 rounded-md border border-border bg-surface p-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <h3 className="text-label font-semibold text-foreground">
                История аудиторий: {historyStudentName}
              </h3>
              <p className="text-caption text-muted-foreground">
                Только подтверждённые планы прошлых и текущего очных занятий.
              </p>
            </div>
            <Button
              onClick={() => {
                setHistoryStudentName(null)
                historyMutation.reset()
              }}
              size="xs"
              type="button"
              variant="ghost"
            >
              Закрыть
            </Button>
          </div>
          {historyMutation.isPending ? (
            <p className="text-small text-muted-foreground">Загружаем историю…</p>
          ) : historyMutation.error ? (
            <p className="text-small text-status-danger-foreground">
              {describeError(historyMutation.error)}
            </p>
          ) : historyMutation.data?.items.length ? (
            <ul className="divide-y divide-border">
              {historyMutation.data.items.map((item) => (
                <li
                  className="flex flex-wrap justify-between gap-x-4 gap-y-1 py-1.5 text-small"
                  key={item.planPublicId}
                >
                  <span className="font-medium text-foreground">
                    {item.eventName} · {item.classroomName}
                  </span>
                  <span className="text-muted-foreground">
                    {item.courseName} · {item.groupName} ·{' '}
                    {new Date(item.startsAt).toLocaleDateString('ru-RU')}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-small text-muted-foreground">Подтверждённых назначений пока нет.</p>
          )}
        </section>
      ) : null}
      <ClassroomStudentPlanner
        groups={groups}
        incidents={incidents}
        lessonLabel={`${plan.event.name} · ${new Date(plan.event.startsAt).toLocaleString('ru-RU', { dateStyle: 'medium', timeStyle: 'short' })}`}
        onConfirm={() => mutation.mutate('confirm')}
        onMove={move}
        onRecalculate={() => mutation.mutate('recalculate')}
        onRequestGroupChange={(studentId, groupId, classroomId) =>
          setGroupChangeRequested({ studentId, groupId, classroomId })
        }
        onShowHistory={(studentId) => {
          const student = students.find((item) => item.id === studentId)
          if (student === undefined || currentPlan === null) return
          setHistoryStudentName(student.name)
          historyMutation.mutate(studentId)
        }}
        pending={mutation.isPending}
        rooms={rooms}
        state={currentPlan?.state ?? 'draft'}
        students={students}
        version={currentPlan?.version ?? 0}
        {...(currentPlan?.staleReason === null || currentPlan?.staleReason === undefined
          ? {}
          : { staleReason: currentPlan.staleReason })}
      />
    </div>
  )
}

export function StaffClassroomAssignments({ eventPublicId }: { eventPublicId: string }) {
  const authentication = useAuthentication()
  const principal = useAuthenticatedPrincipal()
  if (principal.audience !== 'staff') throw new Error('Classroom assignments require Staff auth')
  const queryClient = useQueryClient()
  const client = useMemo(
    () =>
      createClassroomClient(authentication.client.runtime, {
        refreshSession: () => authentication.refresh(),
      }),
    [authentication],
  )
  const queryKey = classroomQueryKeys.assignmentPlan(principal, eventPublicId)
  const query = useQuery({
    queryKey,
    queryFn: ({ signal }) => client.getAssignmentPlan(eventPublicId, { signal }),
    meta: { realtimeResources: ['classroom-assignment-plans'] },
  })

  if (query.isPending) return <PageStatePanel state="loading" />
  if (query.error) {
    return (
      <Alert role="alert" tone="danger">
        <AlertContent>
          <AlertTitle>
            {query.error instanceof ApiResponseError && query.error.status === 403
              ? 'Недостаточно прав'
              : 'Не удалось загрузить план'}
          </AlertTitle>
          <AlertDescription>{describeError(query.error)}</AlertDescription>
        </AlertContent>
      </Alert>
    )
  }

  return (
    <AssignmentEditor
      client={client}
      eventPublicId={eventPublicId}
      key={`${eventPublicId}:${query.data.assignmentPlan.plan?.publicId ?? 'empty'}:${query.data.assignmentPlan.plan?.version ?? 0}`}
      onChanged={async () => queryClient.invalidateQueries({ queryKey })}
      plan={query.data.assignmentPlan}
      storageKey={`vmsh-179:classroom-assignments:${authentication.client.runtime.instance}:${principal.accountId}:${eventPublicId}`}
    />
  )
}
