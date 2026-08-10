import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useMemo, useState, type FormEvent } from 'react'

import {
  PageLayout,
  PageStatePanel,
  createAdminCourseClient,
  useAdminCourseCatalogQuery,
  useAuthenticatedPrincipal,
  useAuthentication,
  useStaffAccessQuery,
} from '@vmsh/app-shell'
import {
  ApiResponseError,
  createBrowserStorageNamespace,
  staffAccessQueryKey,
  type AdminCourse,
  type CreateStaffMemberRequest,
  type ReplaceStaffScopesRequest,
  type StaffAccessMember,
  type StaffScopeSelection,
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

import {
  clearStaffAccessDraft,
  readStaffAccessDraft,
  staffAccessDraftKey,
  writeStaffAccessDraft,
} from './staff-access-draft'
import { UsersSectionTabs, type UsersSection } from './users-section-tabs'

interface SaveStaffAccessCommand {
  member: StaffAccessMember
  input: ReplaceStaffScopesRequest
  draftKey: string
}

function TeacherCreator({
  error,
  saving,
  onCancel,
  onSave,
}: {
  error: Error | null
  saving: boolean
  onCancel: () => void
  onSave: (input: CreateStaffMemberRequest) => void
}) {
  const [draft, setDraft] = useState<CreateStaffMemberRequest>({
    schemaVersion: 1,
    surname: '',
    name: '',
    middleName: null,
    username: '',
    password: '',
  })

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    onSave(draft)
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Новый преподаватель</CardTitle>
      </CardHeader>
      <CardContent>
        <form className="grid gap-3 md:grid-cols-2" onSubmit={submit}>
          <Label className="grid gap-1">
            Фамилия
            <Input
              disabled={saving}
              onChange={(event) => setDraft({ ...draft, surname: event.target.value })}
              required
              value={draft.surname}
            />
          </Label>
          <Label className="grid gap-1">
            Имя
            <Input
              disabled={saving}
              onChange={(event) => setDraft({ ...draft, name: event.target.value })}
              required
              value={draft.name}
            />
          </Label>
          <Label className="grid gap-1">
            Отчество
            <Input
              disabled={saving}
              onChange={(event) => setDraft({ ...draft, middleName: event.target.value || null })}
              value={draft.middleName ?? ''}
            />
          </Label>
          <Label className="grid gap-1">
            Логин
            <Input
              autoComplete="off"
              disabled={saving}
              onChange={(event) => setDraft({ ...draft, username: event.target.value })}
              required
              value={draft.username}
            />
          </Label>
          <Label className="grid gap-1 md:col-span-2">
            Временный пароль
            <Input
              autoComplete="new-password"
              disabled={saving}
              minLength={8}
              onChange={(event) => setDraft({ ...draft, password: event.target.value })}
              required
              type="password"
              value={draft.password}
            />
          </Label>
          {error ? (
            <p className="text-small text-status-error md:col-span-2" role="alert">
              {errorMessage(error)}
            </p>
          ) : null}
          <div className="flex gap-2 md:col-span-2">
            <Button disabled={saving} type="submit">
              {saving ? 'Создаём…' : 'Создать преподавателя'}
            </Button>
            <Button disabled={saving} onClick={onCancel} type="button" variant="outline">
              Отмена
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  )
}

function fullName(member: StaffAccessMember): string {
  return [member.surname, member.name, member.middleName].filter(Boolean).join(' ')
}

function scopeCountLabel(count: number): string {
  const lastTwo = count % 100
  const last = count % 10
  const noun =
    lastTwo >= 11 && lastTwo <= 14
      ? 'областей'
      : last === 1
        ? 'область'
        : last >= 2 && last <= 4
          ? 'области'
          : 'областей'
  return `${count} ${noun}`
}

function scopeKey(scope: StaffScopeSelection): string {
  return `${scope.courseId}\0${scope.groupId ?? ''}`
}

function normalized(scopes: StaffScopeSelection[]): StaffScopeSelection[] {
  return [...scopes].sort((left, right) => scopeKey(left).localeCompare(scopeKey(right)))
}

function StaffScopeEditor({
  accountId,
  courses,
  member,
  saving,
  storageNamespace,
  onSave,
}: {
  accountId: string
  courses: AdminCourse[]
  member: StaffAccessMember
  saving: boolean
  storageNamespace: string
  onSave: (command: SaveStaffAccessCommand) => void
}) {
  const fallback = member.scopes.map(({ courseId, groupId }) => ({ courseId, groupId }))
  const draftKey = staffAccessDraftKey(
    storageNamespace,
    accountId,
    member.staffUserId,
    member.scopes,
  )
  const [draft, setDraft] = useState(() =>
    readStaffAccessDraft(globalThis.localStorage, draftKey, fallback),
  )
  const [storageAvailable, setStorageAvailable] = useState(true)
  const changed = JSON.stringify(normalized(draft)) !== JSON.stringify(normalized(fallback))
  const selected = new Set(draft.map(scopeKey))

  function update(next: StaffScopeSelection[]) {
    const value = normalized(next)
    setDraft(value)
    setStorageAvailable(writeStaffAccessDraft(globalThis.localStorage, draftKey, value))
  }

  function toggleCourse(courseId: string, checked: boolean) {
    const withoutCourse = draft.filter((scope) => scope.courseId !== courseId)
    update(checked ? [...withoutCourse, { courseId, groupId: null }] : withoutCourse)
  }

  function toggleGroup(courseId: string, groupId: string, checked: boolean) {
    const withoutCourseWide = draft.filter(
      (scope) => !(scope.courseId === courseId && scope.groupId === null),
    )
    const key = scopeKey({ courseId, groupId })
    const withoutGroup = withoutCourseWide.filter((scope) => scopeKey(scope) !== key)
    update(checked ? [...withoutGroup, { courseId, groupId }] : withoutGroup)
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    onSave({
      member,
      draftKey,
      input: {
        schemaVersion: 1,
        expectedScopes: member.scopes.map(({ courseId, groupId, version }) => ({
          courseId,
          groupId,
          version,
        })),
        scopes: draft,
      },
    })
  }

  return (
    <form className="space-y-4" onSubmit={submit}>
      <div className="grid gap-3 xl:grid-cols-2">
        {courses.map((course) => {
          const wholeCourse = selected.has(scopeKey({ courseId: course.courseId, groupId: null }))
          return (
            <Card
              aria-label={`Доступ к курсу «${course.name}»`}
              className="min-w-0"
              key={course.courseId}
              role="group"
            >
              <CardHeader className="gap-2 pb-3">
                <div className="flex items-center justify-between gap-3">
                  <CardTitle className="text-body">{course.name}</CardTitle>
                  {course.status !== 'active' ? <Badge>{course.status}</Badge> : null}
                </div>
                <Label className="flex items-center gap-2 text-small font-medium">
                  <Checkbox
                    checked={wholeCourse}
                    disabled={saving || course.status !== 'active'}
                    onCheckedChange={(checked) => toggleCourse(course.courseId, checked === true)}
                  />
                  Весь курс
                </Label>
              </CardHeader>
              <CardContent className="flex flex-wrap gap-x-5 gap-y-2 pt-0">
                {course.groups.map((group) => (
                  <Label className="flex items-center gap-2 text-small" key={group.groupId}>
                    <Checkbox
                      checked={
                        wholeCourse ||
                        selected.has(
                          scopeKey({ courseId: course.courseId, groupId: group.groupId }),
                        )
                      }
                      disabled={saving || wholeCourse || group.status !== 'active'}
                      onCheckedChange={(checked) =>
                        toggleGroup(course.courseId, group.groupId, checked === true)
                      }
                    />
                    {group.shortCode} · {group.name}
                    {group.status !== 'active' ? ' (архив)' : ''}
                  </Label>
                ))}
              </CardContent>
            </Card>
          )
        })}
      </div>

      {!storageAvailable ? (
        <p className="text-small text-status-error" role="alert">
          Черновик не сохраняется в этом браузере. Не закрывайте вкладку до отправки.
        </p>
      ) : changed ? (
        <p className="text-caption text-muted-foreground" role="status">
          Несохранённые изменения хранятся на этом устройстве.
        </p>
      ) : null}

      <Button disabled={saving || !changed} type="submit">
        {saving ? 'Сохраняем…' : 'Сохранить доступы'}
      </Button>
    </form>
  )
}

export function StaffAccessView({
  accountId,
  courses,
  members,
  saving = false,
  storageNamespace,
  onSave,
}: {
  accountId: string
  courses: AdminCourse[]
  members: StaffAccessMember[]
  saving?: boolean
  storageNamespace: string
  onSave: (command: SaveStaffAccessCommand) => void
}) {
  const [query, setQuery] = useState('')
  const [selectedId, setSelectedId] = useState<string>()
  const words = query.trim().toLocaleLowerCase('ru')
  const matches = members.filter((member) =>
    fullName(member).toLocaleLowerCase('ru').includes(words),
  )
  const selected = matches.find((member) => member.staffUserId === selectedId) ?? matches[0]

  return (
    <div className="grid min-h-[34rem] gap-4 lg:grid-cols-[20rem_minmax(0,1fr)]">
      <Card className="min-w-0">
        <CardHeader className="gap-3">
          <CardTitle>Сотрудники</CardTitle>
          <Label className="grid gap-1 text-small">
            Поиск по имени
            <Input
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Фамилия или имя"
              type="search"
              value={query}
            />
          </Label>
          <p className="text-caption text-muted-foreground">Найдено: {matches.length}</p>
        </CardHeader>
        <CardContent className="max-h-[48rem] overflow-y-auto px-2 pb-2">
          <ol className="space-y-1">
            {matches.map((member) => (
              <li key={member.staffUserId}>
                <button
                  aria-current={selected?.staffUserId === member.staffUserId ? 'true' : undefined}
                  className="w-full rounded-md border border-transparent px-3 py-2 text-left hover:bg-muted aria-current:border-border aria-current:bg-muted"
                  onClick={() => setSelectedId(member.staffUserId)}
                  type="button"
                >
                  <span className="block text-small font-medium">{fullName(member)}</span>
                  <span className="mt-1 flex gap-2 text-caption text-muted-foreground">
                    <span>{member.role === 'admin' ? 'Администратор' : 'Преподаватель'}</span>
                    <span>·</span>
                    <span>{scopeCountLabel(member.scopes.length)}</span>
                  </span>
                </button>
              </li>
            ))}
          </ol>
        </CardContent>
      </Card>

      {selected ? (
        <div className="min-w-0 space-y-4">
          <Card>
            <CardHeader className="gap-2">
              <div className="flex flex-wrap items-center gap-2">
                <CardTitle>{fullName(selected)}</CardTitle>
                <Badge variant={selected.account?.status === 'active' ? 'success' : 'warning'}>
                  {selected.account?.status === 'active'
                    ? 'Web-вход активен'
                    : 'Web-вход недоступен'}
                </Badge>
              </div>
              <p className="text-small text-muted-foreground">
                {selected.account?.username ?? 'Staff-аккаунт ещё не создан'}
              </p>
            </CardHeader>
          </Card>

          {selected.role === 'admin' ? (
            <Alert>
              <AlertContent>
                <AlertTitle>Администратор видит все курсы и группы</AlertTitle>
                <AlertDescription>
                  Его глобальный доступ определяется ролью и здесь не редактируется.
                </AlertDescription>
              </AlertContent>
            </Alert>
          ) : (
            <StaffScopeEditor
              accountId={accountId}
              courses={courses}
              key={`${selected.staffUserId}:${selected.scopes.map((scope) => scope.version).join('.')}`}
              member={selected}
              onSave={onSave}
              saving={saving}
              storageNamespace={storageNamespace}
            />
          )}
        </div>
      ) : (
        <Card>
          <CardContent className="pt-5 text-small text-muted-foreground">
            Сотрудники не найдены.
          </CardContent>
        </Card>
      )}
    </div>
  )
}

function errorMessage(error: Error): string {
  return error instanceof ApiResponseError
    ? error.message
    : 'Проверьте соединение и повторите попытку.'
}

/** Phase 10 Staff scope editor; capabilities remain fixed by the teacher role. */
export function StaffAccessPage({
  onSectionChange,
}: {
  onSectionChange: (section: UsersSection) => void
}) {
  const authentication = useAuthentication()
  const principal = useAuthenticatedPrincipal()
  if (principal.audience !== 'staff') throw new Error('Staff access requires Staff auth')
  const isAdmin = principal.role === 'admin'
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
  const directory = useStaffAccessQuery(client, scope, isAdmin)
  const catalog = useAdminCourseCatalogQuery(client, scope, undefined, isAdmin)
  const queryClient = useQueryClient()
  const [creatorOpen, setCreatorOpen] = useState(false)
  const createMutation = useMutation({
    mutationFn: (input: CreateStaffMemberRequest) => client.createStaffMember(input),
    onSuccess: async () => {
      setCreatorOpen(false)
      await queryClient.invalidateQueries({ queryKey: staffAccessQueryKey(scope) })
    },
    onError: (error) => authentication.handleApiError(error),
  })
  const mutation = useMutation({
    mutationFn: (command: SaveStaffAccessCommand) =>
      client.replaceStaffScopes(command.member.staffUserId, command.input),
    onSuccess: async (_, command) => {
      clearStaffAccessDraft(globalThis.localStorage, command.draftKey)
      await queryClient.invalidateQueries({ queryKey: staffAccessQueryKey(scope) })
    },
    onError: (error) => authentication.handleApiError(error),
  })

  if (!isAdmin) {
    return (
      <PageLayout title="Преподаватели и доступы" width="wide">
        <UsersSectionTabs onChange={onSectionChange} section="students" showTeachers={false} />
        <PageStatePanel state="forbidden" />
      </PageLayout>
    )
  }
  if (directory.isPending || catalog.isPending) {
    return (
      <PageLayout title="Преподаватели и доступы" width="wide">
        <PageStatePanel state="loading" />
      </PageLayout>
    )
  }
  const error = directory.error ?? catalog.error
  if (error || !directory.data || !catalog.data) {
    return (
      <PageLayout title="Преподаватели и доступы" width="wide">
        <PageStatePanel
          actionLabel="Повторить"
          onAction={() => void Promise.all([directory.refetch(), catalog.refetch()])}
          state={error instanceof ApiResponseError && error.status === 403 ? 'forbidden' : 'error'}
        />
      </PageLayout>
    )
  }

  return (
    <PageLayout
      description="Выберите, какие курсы целиком или отдельные группы доступны преподавателю."
      eyebrow="Admin"
      title="Преподаватели и доступы"
      width="wide"
    >
      <div className="space-y-4">
        <UsersSectionTabs onChange={onSectionChange} section="teachers" showImports showTeachers />
        <div className="flex justify-end">
          <Button onClick={() => setCreatorOpen(true)} size="sm">
            Добавить преподавателя
          </Button>
        </div>
        {creatorOpen ? (
          <TeacherCreator
            error={createMutation.error}
            onCancel={() => setCreatorOpen(false)}
            onSave={(input) => createMutation.mutate(input)}
            saving={createMutation.isPending}
          />
        ) : null}
        <Alert>
          <AlertContent>
            <AlertTitle>Возможности преподавателя фиксированы ролью</AlertTitle>
            <AlertDescription>
              Здесь настраивается только область данных: весь курс или выбранные группы. Рассылки,
              аудитории, аудит и административные настройки преподавателю недоступны.
            </AlertDescription>
          </AlertContent>
        </Alert>
        {mutation.error ? (
          <Alert role="alert" tone="danger">
            <AlertContent>
              <AlertTitle>Доступы не сохранены</AlertTitle>
              <AlertDescription>{errorMessage(mutation.error)}</AlertDescription>
            </AlertContent>
          </Alert>
        ) : null}
        <StaffAccessView
          accountId={principal.accountId}
          courses={catalog.data.courses}
          members={directory.data.members}
          onSave={(command) => mutation.mutate(command)}
          saving={mutation.isPending}
          storageNamespace={createBrowserStorageNamespace(authentication.client.runtime)}
        />
      </div>
    </PageLayout>
  )
}
