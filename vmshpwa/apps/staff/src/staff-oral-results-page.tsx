import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useEffect, useMemo, useState } from 'react'

import {
  PageLayout,
  PageStatePanel,
  createStaffOralResultClient,
  useAuthenticatedPrincipal,
  useAuthentication,
  useStaffOralRosterQuery,
} from '@vmsh/app-shell'
import {
  ApiResponseError,
  oralResultQueryKeys,
  type RecordOralResultRequest,
} from '@vmsh/contracts'
import { OralResultForm, type OralMarkValue } from '@vmsh/product'
import { Alert, AlertContent, AlertDescription } from '@vmsh/ui'

interface OralResultDraft {
  studentId: string
  marks: Record<string, OralMarkValue>
  reactionId: RecordOralResultRequest['reactionId']
  idempotencyKey: string
}

function emptyDraft(): OralResultDraft {
  return {
    studentId: '',
    marks: {},
    reactionId: null,
    idempotencyKey: crypto.randomUUID(),
  }
}

function readDraft(key: string): OralResultDraft {
  try {
    const value: unknown = JSON.parse(globalThis.localStorage.getItem(key) ?? 'null')
    if (
      value &&
      typeof value === 'object' &&
      'studentId' in value &&
      typeof value.studentId === 'string' &&
      'marks' in value &&
      value.marks &&
      typeof value.marks === 'object' &&
      Object.values(value.marks).every(
        (mark) => mark === 'unmarked' || mark === 'accepted' || mark === 'rejected',
      ) &&
      'reactionId' in value &&
      (value.reactionId === null || [300, 301, 302, 303].includes(Number(value.reactionId))) &&
      'idempotencyKey' in value &&
      typeof value.idempotencyKey === 'string' &&
      value.idempotencyKey.length > 0
    ) {
      return value as OralResultDraft
    }
  } catch {
    // The form still works in memory when storage is unavailable or corrupt.
  }
  return emptyDraft()
}

export function StaffOralResultsPage({ groupLessonId }: { groupLessonId: string }) {
  const authentication = useAuthentication()
  const principal = useAuthenticatedPrincipal()
  if (principal.audience !== 'staff') throw new Error('Oral results require Staff auth')
  const allowed = principal.capabilities.includes('oral.manage')
  const storageKey = `vmshpwa:staff:${principal.accountId}:oral-result-draft:${groupLessonId}`
  const [draft, setDraft] = useState<OralResultDraft>(() => readDraft(storageKey))
  const client = useMemo(
    () =>
      createStaffOralResultClient(authentication.client.runtime, {
        refreshSession: async () => {
          try {
            return await authentication.refresh()
          } catch (error) {
            authentication.handleApiError(error)
            throw error
          }
        },
      }),
    [authentication],
  )
  const queryClient = useQueryClient()
  const queryKey = oralResultQueryKeys.staffRoster(principal, groupLessonId)
  const query = useStaffOralRosterQuery(client, principal, groupLessonId, allowed)

  useEffect(() => {
    try {
      globalThis.localStorage.setItem(storageKey, JSON.stringify(draft))
    } catch {
      // Keep the in-memory draft when browser storage is unavailable.
    }
  }, [draft, storageKey])

  const mutation = useMutation({
    mutationFn: (input: RecordOralResultRequest) => client.record(groupLessonId, input),
    onSuccess: async () => {
      setDraft(emptyDraft())
      try {
        globalThis.localStorage.removeItem(storageKey)
      } catch {
        // The successful server write is authoritative.
      }
      await queryClient.invalidateQueries({ queryKey })
    },
    onError: (error) => authentication.handleApiError(error),
  })

  if (!allowed) {
    return (
      <PageLayout title="Устный приём" width="wide">
        <PageStatePanel state="forbidden" />
      </PageLayout>
    )
  }

  const submit = () => {
    const marks = Object.entries(draft.marks).flatMap(([problemId, outcome]) =>
      outcome === 'unmarked' ? [] : [{ problemId, outcome }],
    )
    if (!draft.studentId || marks.length === 0) return
    mutation.mutate({
      schemaVersion: 1,
      studentId: draft.studentId,
      idempotencyKey: draft.idempotencyKey,
      marks,
      reactionId: draft.reactionId,
    })
  }

  return (
    <PageLayout
      description="Выберите школьника, отметьте принятые задачи и сохраните один раунд. Черновик не теряется при перезагрузке."
      eyebrow={`Групповое занятие ${groupLessonId}`}
      title="Результаты устного приёма"
      width="wide"
    >
      {query.isPending ? <PageStatePanel state="loading" /> : null}
      {query.error ? <PageStatePanel state="error" /> : null}
      {query.data && (query.data.students.length === 0 || query.data.problems.length === 0) ? (
        <Alert tone="info">
          <AlertContent>
            <AlertDescription>
              Нет online-школьников или опубликованных устных задач для этого занятия.
            </AlertDescription>
          </AlertContent>
        </Alert>
      ) : null}
      {query.data && query.data.students.length > 0 && query.data.problems.length > 0 ? (
        <OralResultForm
          busy={mutation.isPending}
          marks={draft.marks}
          onMarkChange={(problemId, value) =>
            setDraft((current) => ({
              ...current,
              marks: { ...current.marks, [problemId]: value },
            }))
          }
          onReactionChange={(reactionId) => {
            if (reactionId !== null && ![300, 301, 302, 303].includes(reactionId)) return
            setDraft((current) => ({
              ...current,
              reactionId: reactionId as RecordOralResultRequest['reactionId'],
            }))
          }}
          onStudentChange={(studentId) =>
            setDraft((current) => ({ ...current, studentId, marks: {}, reactionId: null }))
          }
          onSubmit={submit}
          problems={query.data.problems}
          reactionId={draft.reactionId}
          studentId={draft.studentId}
          students={query.data.students}
        />
      ) : null}
      {mutation.error ? (
        <p className="text-small text-destructive" role="alert">
          {mutation.error instanceof ApiResponseError
            ? mutation.error.message
            : 'Не удалось сохранить устные результаты.'}
        </p>
      ) : null}
      {mutation.isSuccess ? (
        <p className="text-small text-status-success" role="status">
          Результаты сохранены.
        </p>
      ) : null}
    </PageLayout>
  )
}
