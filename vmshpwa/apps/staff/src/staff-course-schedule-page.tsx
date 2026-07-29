import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useMemo, useState } from 'react'

import {
  PageLayout,
  PageStatePanel,
  createAdminCourseClient,
  useAdminCourseCatalogQuery,
  useAdminCourseScheduleQuery,
  useAdminGroupScheduleQuery,
  useAuthenticatedPrincipal,
  useAuthentication,
} from '@vmsh/app-shell'
import {
  ApiResponseError,
  adminCourseScheduleQueryKey,
  adminGroupScheduleQueryKey,
  type AdminCourseScheduleRule,
  type AdminGroupScheduleOverride,
  type SaveAdminCourseScheduleRule,
  type SaveAdminGroupScheduleOverride,
  type ScheduleField,
} from '@vmsh/contracts'
import {
  Alert,
  AlertContent,
  AlertDescription,
  AlertTitle,
  Badge,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Label,
} from '@vmsh/ui'

import { clearScheduleDraft, scheduleFieldLabels } from './course-schedule-draft'
import { CourseScheduleEditor } from './course-schedule-editor'

const fields: ScheduleField[] = [
  'opens_at',
  'hint_scheduled_at',
  'submission_closes_at',
  'solution_scheduled_at',
]

type Editor = { owner: 'course'; field: ScheduleField } | { owner: 'group'; field: ScheduleField }

type Command =
  | {
      kind: 'create-course'
      courseId: string
      input: SaveAdminCourseScheduleRule
      storageKey: string
    }
  | { kind: 'confirm-course'; rule: AdminCourseScheduleRule }
  | {
      kind: 'create-group'
      groupId: string
      input: SaveAdminGroupScheduleOverride
      storageKey: string
    }
  | { kind: 'confirm-group'; override: AdminGroupScheduleOverride }

function activeRule(rules: AdminCourseScheduleRule[], field: ScheduleField) {
  return rules.find((rule) => rule.field === field && rule.state === 'active')
}

function draftRule(rules: AdminCourseScheduleRule[], field: ScheduleField) {
  return rules.find((rule) => rule.field === field && rule.state === 'draft')
}

function activeOverride(overrides: AdminGroupScheduleOverride[], field: ScheduleField) {
  return overrides.find((override) => override.field === field && override.state === 'active')
}

function draftOverride(overrides: AdminGroupScheduleOverride[], field: ScheduleField) {
  return overrides.find((override) => override.field === field && override.state === 'draft')
}

function valueLabel(value?: {
  dayOffset: number | null
  localTime: string | null
  timezone: string | null
}) {
  if (!value || value.dayOffset === null || value.localTime === null) return '—'
  const day =
    value.dayOffset === 0
      ? 'в день цикла'
      : `${value.dayOffset > 0 ? '+' : ''}${value.dayOffset} д.`
  return `${day} · ${value.localTime.slice(0, 5)}`
}

function errorMessage(error: Error): string {
  return error instanceof ApiResponseError
    ? error.message
    : 'Проверьте соединение и повторите попытку.'
}

export function StaffCourseSchedulePage({
  requestedCourseId,
  requestedGroupId,
  onCourseChange,
  onGroupChange,
}: {
  requestedCourseId?: string
  requestedGroupId?: string
  onCourseChange: (courseId: string) => void
  onGroupChange: (groupId: string) => void
}) {
  const authentication = useAuthentication()
  const principal = useAuthenticatedPrincipal()
  if (principal.audience !== 'staff') throw new Error('Course schedules require Staff auth')
  const client = useMemo(
    () =>
      createAdminCourseClient(authentication.client.runtime, {
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
  const scope = { audience: 'staff' as const, accountId: principal.accountId }
  const catalog = useAdminCourseCatalogQuery(client, scope)
  const selectedCourse =
    catalog.data?.courses.find((course) => course.courseId === requestedCourseId) ??
    catalog.data?.courses[0]
  const selectedGroup =
    selectedCourse?.groups.find((group) => group.groupId === requestedGroupId) ??
    selectedCourse?.groups[0]
  const courseSchedule = useAdminCourseScheduleQuery(
    client,
    scope,
    selectedCourse?.courseId ?? null,
  )
  const selectedGroupSchedule = useAdminGroupScheduleQuery(
    client,
    scope,
    selectedGroup?.groupId ?? null,
  )
  const queryClient = useQueryClient()
  const [editor, setEditor] = useState<Editor | null>(null)

  const mutation = useMutation<unknown, Error, Command>({
    mutationFn: (command) => {
      if (command.kind === 'create-course')
        return client.createCourseScheduleDraft(command.courseId, command.input)
      if (command.kind === 'confirm-course')
        return client.confirmCourseScheduleRule(command.rule.ruleId, command.rule.version)
      if (command.kind === 'create-group')
        return client.createGroupScheduleDraft(command.groupId, command.input)
      return client.confirmGroupScheduleOverride(
        command.override.overrideId,
        command.override.version,
      )
    },
    onSuccess: async (_, command) => {
      if ('storageKey' in command) clearScheduleDraft(command.storageKey)
      setEditor(null)
      if (selectedCourse)
        await queryClient.invalidateQueries({
          queryKey: adminCourseScheduleQueryKey(scope, selectedCourse.courseId),
        })
      await Promise.all(
        (selectedCourse?.groups ?? []).map((group) =>
          queryClient.invalidateQueries({
            queryKey: adminGroupScheduleQueryKey(scope, group.groupId),
          }),
        ),
      )
    },
    onError: (error) => authentication.handleApiError(error),
  })

  if (
    catalog.isPending ||
    (selectedCourse && courseSchedule.isPending) ||
    (selectedGroup && selectedGroupSchedule.isPending)
  ) {
    return (
      <PageLayout title="Расписание" width="wide">
        <PageStatePanel state="loading" />
      </PageLayout>
    )
  }
  if (catalog.error || courseSchedule.error || selectedGroupSchedule.error) {
    const error = catalog.error ?? courseSchedule.error ?? selectedGroupSchedule.error
    return (
      <PageLayout title="Расписание" width="wide">
        <PageStatePanel
          state={error instanceof ApiResponseError && error.status === 403 ? 'forbidden' : 'error'}
        />
      </PageLayout>
    )
  }
  if (!selectedCourse || !courseSchedule.data) {
    return (
      <PageLayout title="Расписание" width="wide">
        <PageStatePanel state="empty" />
      </PageLayout>
    )
  }

  const selectedRules = courseSchedule.data.rules
  const selectedOverrides = selectedGroupSchedule.data?.overrides ?? []
  const editorField = editor?.field
  const courseInitial = editorField ? activeRule(selectedRules, editorField) : undefined
  const groupInitialOverride = editorField
    ? activeOverride(selectedOverrides, editorField)
    : undefined
  const groupInitialCourse = editorField ? activeRule(selectedRules, editorField) : undefined
  const draftBaseVersion =
    editor?.owner === 'course'
      ? (courseInitial?.version ?? 0)
      : (groupInitialOverride?.version ?? groupInitialCourse?.version ?? 0)
  const draftOwnerId = editor?.owner === 'course' ? selectedCourse.courseId : selectedGroup?.groupId
  const storageKey = `${authentication.client.runtime.instance}:staff:${principal.accountId}:schedule:${editor?.owner ?? 'none'}:${draftOwnerId ?? 'none'}:${editorField ?? 'none'}:${draftBaseVersion}`
  const editorInitial =
    editor?.owner === 'course'
      ? courseInitial
      : groupInitialOverride?.mode === 'override'
        ? {
            dayOffset: groupInitialOverride.dayOffset!,
            localTime: groupInitialOverride.localTime!,
            timezone: groupInitialOverride.timezone!,
          }
        : groupInitialCourse
  const editorMode =
    editor?.owner === 'group' ? (groupInitialOverride?.mode ?? ('inherit' as const)) : undefined

  return (
    <PageLayout
      description="Шаблон курса и переопределения групп. Уже созданные занятия не сдвигаются автоматически."
      eyebrow={catalog.data.season.title}
      title="Расписание"
      width="wide"
    >
      <div className="space-y-5">
        <div className="grid gap-3 sm:grid-cols-2">
          <Label className="grid gap-1">
            Курс
            <select
              className="min-h-10 rounded-md border border-input bg-surface px-3 text-small"
              onChange={(event) => onCourseChange(event.target.value)}
              value={selectedCourse.courseId}
            >
              {catalog.data.courses.map((course) => (
                <option key={course.courseId} value={course.courseId}>
                  {course.name}
                </option>
              ))}
            </select>
          </Label>
          <Label className="grid gap-1">
            Группа для переопределений
            <select
              className="min-h-10 rounded-md border border-input bg-surface px-3 text-small"
              disabled={selectedCourse.groups.length === 0}
              onChange={(event) => onGroupChange(event.target.value)}
              value={selectedGroup?.groupId ?? ''}
            >
              {selectedCourse.groups.map((group) => (
                <option key={group.groupId} value={group.groupId}>
                  {group.name}
                </option>
              ))}
            </select>
          </Label>
        </div>

        {mutation.error ? (
          <Alert role="alert" tone="danger">
            <AlertContent>
              <AlertTitle>Расписание не изменено</AlertTitle>
              <AlertDescription>{errorMessage(mutation.error)}</AlertDescription>
            </AlertContent>
          </Alert>
        ) : null}

        <Card>
          <CardHeader>
            <CardTitle>Шаблон курса</CardTitle>
          </CardHeader>
          <CardContent className="divide-y divide-border p-0">
            {fields.map((field) => {
              const active = activeRule(selectedRules, field)
              const draft = draftRule(selectedRules, field)
              const impact = courseSchedule.data.draftImpacts.find(
                (item) => item.ruleId === draft?.ruleId,
              )
              return (
                <div className="flex flex-wrap items-center gap-3 px-4 py-3" key={field}>
                  <div className="min-w-52 flex-1">
                    <p className="text-small font-medium">{scheduleFieldLabels[field]}</p>
                    <p className="font-num text-caption text-muted-foreground">
                      {valueLabel(active)}
                    </p>
                    {draft ? (
                      <p className="mt-1 text-caption text-status-warning">
                        Черновик: {valueLabel(draft)} · затронет {impact?.groupLessons ?? '—'}{' '}
                        занятий, готовых окон: {impact?.materializedWindows ?? '—'}
                      </p>
                    ) : null}
                  </div>
                  {draft ? (
                    <Button
                      disabled={mutation.isPending}
                      onClick={() => mutation.mutate({ kind: 'confirm-course', rule: draft })}
                      size="sm"
                    >
                      Подтвердить
                    </Button>
                  ) : (
                    <Button
                      onClick={() => setEditor({ owner: 'course', field })}
                      size="sm"
                      variant="outline"
                    >
                      Изменить
                    </Button>
                  )}
                </div>
              )
            })}
          </CardContent>
        </Card>

        {selectedGroup ? (
          <Card>
            <CardHeader>
              <CardTitle>{selectedGroup.name}</CardTitle>
            </CardHeader>
            <CardContent className="divide-y divide-border p-0">
              {fields.map((field) => {
                const course = activeRule(selectedRules, field)
                const active = activeOverride(selectedOverrides, field)
                const draft = draftOverride(selectedOverrides, field)
                const effective =
                  active?.mode === 'override'
                    ? active
                    : active?.mode === 'disabled'
                      ? undefined
                      : course
                return (
                  <div className="flex flex-wrap items-center gap-3 px-4 py-3" key={field}>
                    <div className="min-w-52 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="text-small font-medium">{scheduleFieldLabels[field]}</p>
                        <Badge variant={active ? 'info' : 'neutral'}>
                          {active?.mode === 'override'
                            ? 'Своё время'
                            : active?.mode === 'disabled'
                              ? 'Отключено'
                              : 'Как в курсе'}
                        </Badge>
                      </div>
                      <p className="font-num text-caption text-muted-foreground">
                        {valueLabel(effective)}
                      </p>
                      {draft ? (
                        <p className="mt-1 text-caption text-status-warning">
                          Черновик:{' '}
                          {draft.mode === 'override'
                            ? valueLabel(draft)
                            : draft.mode === 'inherit'
                              ? 'как в курсе'
                              : 'отключено'}
                        </p>
                      ) : null}
                    </div>
                    {draft ? (
                      <Button
                        disabled={mutation.isPending}
                        onClick={() => mutation.mutate({ kind: 'confirm-group', override: draft })}
                        size="sm"
                      >
                        Подтвердить
                      </Button>
                    ) : (
                      <Button
                        onClick={() => setEditor({ owner: 'group', field })}
                        size="sm"
                        variant="outline"
                      >
                        Изменить
                      </Button>
                    )}
                  </div>
                )
              })}
            </CardContent>
          </Card>
        ) : null}
      </div>

      {editor && editorField ? (
        <CourseScheduleEditor
          field={editorField}
          {...(editorInitial === undefined ? {} : { initial: editorInitial })}
          key={storageKey}
          {...(editorMode === undefined ? {} : { mode: editorMode })}
          onOpenChange={(open) => {
            if (!open && !mutation.isPending) setEditor(null)
          }}
          onSave={(input) => {
            if (editor.owner === 'course') {
              mutation.mutate({
                kind: 'create-course',
                courseId: selectedCourse.courseId,
                input: input as SaveAdminCourseScheduleRule,
                storageKey,
              })
            } else if (selectedGroup) {
              mutation.mutate({
                kind: 'create-group',
                groupId: selectedGroup.groupId,
                input: input as SaveAdminGroupScheduleOverride,
                storageKey,
              })
            }
          }}
          open
          saving={mutation.isPending}
          storageKey={storageKey}
        />
      ) : null}
    </PageLayout>
  )
}
