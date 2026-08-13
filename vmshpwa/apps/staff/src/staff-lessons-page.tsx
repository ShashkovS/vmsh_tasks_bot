import { useMutation, useQueryClient } from '@tanstack/react-query'
import { BookOpenCheck, Plus } from 'lucide-react'
import { useEffect, useMemo, useState, type FormEvent } from 'react'

import {
  PageLayout,
  PageStatePanel,
  createAdminCourseClient,
  createStaffDashboardClient,
  useAdminCourseCatalogQuery,
  useAuthenticatedPrincipal,
  useAuthentication,
  useStaffDashboardQuery,
} from '@vmsh/app-shell'
import {
  ApiResponseError,
  staffDashboardQueryKey,
  type AdminGroupLessonResponse,
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
  Checkbox,
  Input,
  Label,
} from '@vmsh/ui'

const phaseLabels = {
  draft: 'Черновик',
  scheduled: 'Запланировано',
  active: 'Приём идёт',
  hints_published: 'Подсказки опубликованы',
  submissions_closed: 'Приём закрыт',
  solutions_published: 'Решения опубликованы',
} as const

const publicationLabels = {
  none: 'Не задано',
  scheduled: 'По расписанию',
  published: 'Опубликовано',
} as const

function PublicationState({ state }: { state: keyof typeof publicationLabels }) {
  return (
    <Badge variant={state === 'published' ? 'success' : state === 'scheduled' ? 'info' : 'neutral'}>
      {publicationLabels[state]}
    </Badge>
  )
}

type LessonDraft = {
  courseId: string
  groupId: string
  lessonNumber: string
  title: string
  cycleAnchorDate: string
  opensLocalTime: string
  submissionClosesLocalTime: string
  hintScheduledLocalTime: string
  solutionScheduledLocalTime: string
  createForAllGroups: boolean
}

const emptyDraft: LessonDraft = {
  courseId: '',
  groupId: '',
  lessonNumber: '0',
  title: '',
  cycleAnchorDate: '',
  opensLocalTime: '',
  submissionClosesLocalTime: '',
  hintScheduledLocalTime: '',
  solutionScheduledLocalTime: '',
  createForAllGroups: true,
}

function lessonCreationError(error: unknown): string {
  return error instanceof ApiResponseError
    ? error.message
    : error instanceof Error && error.message
      ? error.message
      : 'Проверьте обязательные даты и повторите попытку.'
}

function readDraft(key: string): LessonDraft {
  try {
    const stored: unknown = JSON.parse(globalThis.localStorage.getItem(key) ?? 'null')
    return stored && typeof stored === 'object'
      ? { ...emptyDraft, ...(stored as Partial<LessonDraft>) }
      : emptyDraft
  } catch {
    return emptyDraft
  }
}

function LessonCreator({ onClose }: { onClose: () => void }) {
  const authentication = useAuthentication()
  const principal = useAuthenticatedPrincipal()
  const scope = { audience: 'staff' as const, accountId: principal.accountId }
  const draftKey = `vmshpwa:staff:${principal.accountId}:new-group-lesson`
  const [draft, setDraft] = useState<LessonDraft>(() => readDraft(draftKey))
  const client = useMemo(
    () =>
      createAdminCourseClient(authentication.client.runtime, {
        refreshSession: () => authentication.refresh(),
      }),
    [authentication],
  )
  const catalog = useAdminCourseCatalogQuery(client, scope, undefined, true)
  const queryClient = useQueryClient()
  const [creationNotice, setCreationNotice] = useState<string>()
  const selectedCourse =
    catalog.data?.courses.find((course) => course.courseId === draft.courseId) ??
    catalog.data?.courses[0]
  const selectedGroup =
    selectedCourse?.groups.find((group) => group.groupId === draft.groupId) ??
    selectedCourse?.groups[0]
  const mutation = useMutation({
    mutationFn: async () => {
      if (!selectedCourse || !selectedGroup) throw new Error('Сначала создайте группу')
      const groups = draft.createForAllGroups
        ? selectedCourse.groups.filter((group) => group.status === 'active')
        : [selectedGroup]
      const created: AdminGroupLessonResponse[] = []
      const failures: string[] = []
      for (const group of groups) {
        try {
          created.push(
            await client.createGroupLesson({
              schemaVersion: 1,
              courseId: selectedCourse.courseId,
              groupId: group.groupId,
              lessonNumber: Number(draft.lessonNumber),
              title: draft.title.trim() || null,
              cycleAnchorDate: draft.cycleAnchorDate,
              businessTimezone: 'Europe/Moscow',
              opensLocalTime: draft.opensLocalTime || null,
              submissionClosesLocalTime: draft.submissionClosesLocalTime,
              hintScheduledLocalTime: draft.hintScheduledLocalTime || null,
              solutionScheduledLocalTime: draft.solutionScheduledLocalTime || null,
            }),
          )
        } catch (error) {
          failures.push(`${group.shortCode} · ${group.name}: ${lessonCreationError(error)}`)
        }
      }
      if (created.length === 0) throw new Error(failures.join('; ') || 'Занятия не созданы')
      return { created, failures }
    },
    onSuccess: async ({ created, failures }) => {
      await queryClient.invalidateQueries({ queryKey: staffDashboardQueryKey(scope) })
      if (failures.length > 0) {
        setCreationNotice(`Создано: ${created.length}. Не создано: ${failures.join('; ')}`)
        return
      }
      globalThis.localStorage.removeItem(draftKey)
      globalThis.location.assign(
        `/staff/lessons/${encodeURIComponent(created[0]!.groupLesson.groupLessonId)}`,
      )
    },
    onError: (error) => authentication.handleApiError(error),
  })

  useEffect(() => {
    globalThis.localStorage.setItem(draftKey, JSON.stringify(draft))
  }, [draft, draftKey])

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setCreationNotice(undefined)
    mutation.mutate()
  }

  if (catalog.isPending) return <PageStatePanel state="loading" />
  if (catalog.error) return <PageStatePanel state="error" />

  return (
    <Card>
      <CardHeader>
        <CardTitle>Новое занятие группы</CardTitle>
      </CardHeader>
      <CardContent>
        <form className="grid gap-3 md:grid-cols-2" onSubmit={submit}>
          <Label className="grid gap-1">
            Курс
            <select
              className="min-h-10 rounded-md border border-input bg-surface px-3 text-small"
              onChange={(event) =>
                setDraft((value) => ({ ...value, courseId: event.target.value, groupId: '' }))
              }
              value={selectedCourse?.courseId ?? ''}
            >
              {catalog.data?.courses.map((course) => (
                <option key={course.courseId} value={course.courseId}>
                  {course.name}
                </option>
              ))}
            </select>
          </Label>
          <Label className="grid gap-1">
            Группа
            <select
              className="min-h-10 rounded-md border border-input bg-surface px-3 text-small"
              disabled={mutation.isPending || draft.createForAllGroups}
              onChange={(event) => setDraft((value) => ({ ...value, groupId: event.target.value }))}
              value={selectedGroup?.groupId ?? ''}
            >
              {selectedCourse?.groups.map((group) => (
                <option key={group.groupId} value={group.groupId}>
                  {group.shortCode} · {group.name}
                </option>
              ))}
            </select>
          </Label>
          <Label className="flex items-center gap-2 md:col-span-2">
            <Checkbox
              checked={draft.createForAllGroups}
              disabled={mutation.isPending}
              onCheckedChange={(checked) =>
                setDraft((value) => ({ ...value, createForAllGroups: checked === true }))
              }
            />
            Создать занятие сразу для всех активных групп курса
            {selectedCourse
              ? ` (${selectedCourse.groups.filter((group) => group.status === 'active').length})`
              : ''}
          </Label>
          <Label className="grid gap-1">
            Номер занятия
            <Input
              max="10000"
              min="0"
              onChange={(event) =>
                setDraft((value) => ({ ...value, lessonNumber: event.target.value }))
              }
              required
              type="number"
              value={draft.lessonNumber}
            />
          </Label>
          <Label className="grid gap-1">
            Название (необязательно)
            <Input
              onChange={(event) => setDraft((value) => ({ ...value, title: event.target.value }))}
              value={draft.title}
            />
          </Label>
          <Label className="grid gap-1">
            Дата занятия
            <Input
              onChange={(event) =>
                setDraft((value) => ({ ...value, cycleAnchorDate: event.target.value }))
              }
              required
              type="date"
              value={draft.cycleAnchorDate}
            />
          </Label>
          <Label className="grid gap-1">
            Открыть приём · Москва (необязательно)
            <Input
              onChange={(event) =>
                setDraft((value) => ({ ...value, opensLocalTime: event.target.value }))
              }
              type="datetime-local"
              value={draft.opensLocalTime}
            />
          </Label>
          <Label className="grid gap-1">
            Закрыть приём · Москва
            <Input
              onChange={(event) =>
                setDraft((value) => ({ ...value, submissionClosesLocalTime: event.target.value }))
              }
              required
              type="datetime-local"
              value={draft.submissionClosesLocalTime}
            />
          </Label>
          <Label className="grid gap-1">
            Подсказки · Москва (необязательно)
            <Input
              onChange={(event) =>
                setDraft((value) => ({ ...value, hintScheduledLocalTime: event.target.value }))
              }
              type="datetime-local"
              value={draft.hintScheduledLocalTime}
            />
          </Label>
          <Label className="grid gap-1">
            Решения · Москва (необязательно)
            <Input
              onChange={(event) =>
                setDraft((value) => ({ ...value, solutionScheduledLocalTime: event.target.value }))
              }
              type="datetime-local"
              value={draft.solutionScheduledLocalTime}
            />
          </Label>
          <p className="self-end text-caption text-muted-foreground">
            Дедлайн и публикация решений независимы. Расписание можно менять отдельно.
          </p>
          {mutation.error ? (
            <Alert className="md:col-span-2" tone="danger">
              <AlertContent>
                <AlertTitle>Занятие не создано</AlertTitle>
                <AlertDescription>{lessonCreationError(mutation.error)}</AlertDescription>
              </AlertContent>
            </Alert>
          ) : null}
          {creationNotice ? (
            <Alert className="md:col-span-2" tone="warning">
              <AlertContent>
                <AlertTitle>Занятия созданы частично</AlertTitle>
                <AlertDescription>{creationNotice}</AlertDescription>
              </AlertContent>
            </Alert>
          ) : null}
          <div className="flex gap-2 md:col-span-2">
            <Button disabled={mutation.isPending || !selectedGroup} type="submit">
              {mutation.isPending
                ? 'Создаём…'
                : draft.createForAllGroups
                  ? 'Создать для всех групп'
                  : 'Создать и открыть'}
            </Button>
            <Button disabled={mutation.isPending} onClick={onClose} type="button" variant="outline">
              Отмена
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  )
}

/** Production lesson list. Storybook keeps its isolated prototype in pages.tsx. */
export function StaffLessonsPage() {
  const authentication = useAuthentication()
  const principal = useAuthenticatedPrincipal()
  const client = useMemo(
    () =>
      createStaffDashboardClient(authentication.client.runtime, {
        refreshSession: () => authentication.refresh(),
      }),
    [authentication],
  )
  const result = useStaffDashboardQuery(client, {
    audience: 'staff',
    accountId: principal.accountId,
  })
  const [creatorOpen, setCreatorOpen] = useState(false)

  if (result.isPending) {
    return (
      <PageLayout title="Уроки и публикации" width="wide">
        <PageStatePanel state="loading" />
      </PageLayout>
    )
  }
  if (result.error) {
    return (
      <PageLayout title="Уроки и публикации" width="wide">
        <PageStatePanel
          actionLabel="Повторить"
          onAction={() => void result.refetch()}
          state={
            result.error instanceof ApiResponseError && result.error.status === 403
              ? 'forbidden'
              : 'error'
          }
        />
      </PageLayout>
    )
  }

  return (
    <PageLayout
      actions={
        principal.audience === 'staff' && principal.role === 'admin' ? (
          <Button onClick={() => setCreatorOpen((value) => !value)}>
            <Plus /> Создать занятие
          </Button>
        ) : undefined
      }
      description="Здесь отображаются только занятия и публикации, сохранённые в базе данных."
      eyebrow="LaTeX — единственный источник"
      title="Уроки и публикации"
      width="wide"
    >
      {creatorOpen ? (
        <div className="mb-4">
          <LessonCreator onClose={() => setCreatorOpen(false)} />
        </div>
      ) : null}
      {result.data.lessons.length === 0 ? (
        <PageStatePanel
          description="Создайте первое занятие после добавления курсов и групп."
          state="empty"
          title="Занятий пока нет"
        />
      ) : (
        <div className="grid gap-3 lg:grid-cols-2 xl:grid-cols-3">
          {result.data.lessons.map((lesson) => (
            <a
              className="rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              href={`/staff/lessons/${encodeURIComponent(lesson.groupLessonId)}`}
              key={lesson.groupLessonId}
            >
              <Card className="h-full transition-colors hover:border-strong">
                <CardHeader className="space-y-2">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <Badge variant="neutral">{lesson.course.name}</Badge>
                    <Badge variant={lesson.phase === 'draft' ? 'warning' : 'neutral'}>
                      {phaseLabels[lesson.phase]}
                    </Badge>
                  </div>
                  <CardTitle>
                    {lesson.group.name} · занятие {lesson.lessonNumber}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <dl className="grid grid-cols-[auto_1fr] items-center gap-x-3 gap-y-2 text-small">
                    <dt className="text-muted-foreground">Условие</dt>
                    <dd>
                      <PublicationState state={lesson.publications.condition.state} />
                    </dd>
                    <dt className="text-muted-foreground">Подсказка</dt>
                    <dd>
                      <PublicationState state={lesson.publications.hint.state} />
                    </dd>
                    <dt className="text-muted-foreground">Решение</dt>
                    <dd>
                      <PublicationState state={lesson.publications.solution.state} />
                    </dd>
                  </dl>
                  <p className="mt-3 flex items-center gap-2 border-t border-border pt-3 text-caption text-muted-foreground">
                    <BookOpenCheck aria-hidden="true" className="size-4" /> Открыть занятие
                  </p>
                </CardContent>
              </Card>
            </a>
          ))}
        </div>
      )}
    </PageLayout>
  )
}
