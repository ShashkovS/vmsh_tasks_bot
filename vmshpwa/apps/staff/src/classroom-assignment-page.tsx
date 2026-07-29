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
import { Alert, AlertContent, AlertDescription, AlertTitle } from '@vmsh/ui'

function colorIndex(colorKey: string | null): 0 | 1 | 2 | 3 | 4 {
  const match = /^level-([1-4])$/.exec(colorKey ?? '')
  return match ? (Number(match[1]) as 1 | 2 | 3 | 4) : 0
}

function describeError(error: Error): string {
  if (error instanceof ApiResponseError) return error.message
  if (error instanceof ClassroomNetworkError) return 'Проверьте соединение и повторите попытку.'
  return 'Обновите страницу и повторите попытку.'
}

function savedAssignments(storageKey: string): Record<string, string> | null {
  try {
    const raw = globalThis.localStorage.getItem(storageKey)
    if (raw === null) return null
    const parsed: unknown = JSON.parse(raw)
    if (typeof parsed !== 'object' || parsed === null || !('assignments' in parsed)) return null
    const value = (parsed as { assignments?: unknown }).assignments
    if (typeof value !== 'object' || value === null) return null
    return Object.fromEntries(
      Object.entries(value).filter(
        (entry): entry is [string, string] => typeof entry[1] === 'string',
      ),
    )
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
  const [assignments, setAssignments] = useState(saved ?? serverAssignments(plan))
  const [storageFailed, setStorageFailed] = useState(false)
  const [groupChangeRequested, setGroupChangeRequested] = useState(false)

  const groups: ClassroomGroupOption[] = plan.groups.map((group) => ({
    id: group.groupLessonPublicId,
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
  const rooms: ClassroomPlanRoom[] = plan.rooms.map((room) => ({
    id: room.publicId,
    name: room.name,
    groupId: room.groupLessonPublicId,
  }))
  const students: ClassroomPlanStudent[] = plan.students.map((student) => ({
    id: student.enrollmentPublicId,
    name: `${student.surname} ${student.name}`,
    groupId: student.groupLessonPublicId,
    classroomId: assignments[student.enrollmentPublicId] ?? null,
    status: assignments[student.enrollmentPublicId] === undefined ? 'reassigning' : 'assigned',
    source: student.source,
    age: student.age,
    schoolClass: student.grade,
    strength: student.strength,
  }))
  const currentPlan = plan.plan

  const mutation = useMutation({
    mutationFn: async (kind: 'recalculate' | 'confirm') => {
      if (kind === 'recalculate') {
        return client.recalculateAssignmentPlan(
          eventPublicId,
          currentPlan === null
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
          : [{ enrollmentPublicId: student.enrollmentPublicId, classroomPublicId }]
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

  const move = (studentId: string, classroomId: string) => {
    const next = { ...assignments, [studentId]: classroomId }
    setAssignments(next)
    try {
      globalThis.localStorage.setItem(storageKey, JSON.stringify({ assignments: next }))
      setStorageFailed(false)
    } catch {
      setStorageFailed(true)
    }
  }
  const incidents =
    currentPlan === null
      ? [
          {
            id: 'not-calculated',
            title: 'План ещё не рассчитан',
            description: 'Сначала создайте предпросмотр распределения школьников.',
            blocking: true,
          },
        ]
      : []

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
            <AlertTitle>Смена группы требует отдельного подтверждения</AlertTitle>
            <AlertDescription>
              Обычное перемещение не меняет учебную группу школьника. Этот сценарий будет оформлен
              отдельным действием с записью в историю.
            </AlertDescription>
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
      <ClassroomStudentPlanner
        groups={groups}
        incidents={incidents}
        lessonLabel={`${plan.event.name} · ${new Date(plan.event.startsAt).toLocaleString('ru-RU', { dateStyle: 'medium', timeStyle: 'short' })}`}
        onConfirm={() => mutation.mutate('confirm')}
        onMove={move}
        onRecalculate={() => mutation.mutate('recalculate')}
        onRequestGroupChange={() => setGroupChangeRequested(true)}
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
