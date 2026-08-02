import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useVirtualizer } from '@tanstack/react-virtual'
import { useMemo, useRef, useState, type FormEvent } from 'react'

import {
  PageLayout,
  PageStatePanel,
  createAdminCourseClient,
  useAdminCourseCatalogQuery,
  useAdminStudentEnrollmentsQuery,
  useAuthenticatedPrincipal,
  useAuthentication,
} from '@vmsh/app-shell'
import {
  ApiResponseError,
  adminStudentEnrollmentsQueryKey,
  createBrowserStorageNamespace,
  type AdminCourse,
  type AdminEnrollmentGroup,
  type AdminStudentCourseEnrollment,
  type AdminStudentDirectoryEntry,
  type CreateStudentAccountRequest,
  type UpdateAdminStudentEnrollmentRequest,
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
  clearEnrollmentDraft,
  enrollmentDraftKey,
  readEnrollmentDraft,
  writeEnrollmentDraft,
} from './student-enrollment-draft'
import { filterStudents } from './student-directory-search'
import { FamilyAccountManager, type FamilyAccountCommand } from './family-account-manager'
import { StudentAccountControls, type AccountLifecycleCommand } from './student-account-controls'
import {
  StudentAccountBatchPanel,
  type StudentAccountBatchCommand,
  type StudentAccountBatchResult,
} from './student-account-batch-panel'
import { StudentAccountCreator } from './student-account-creator'
import { UsersSectionTabs, type UsersSection } from './users-section-tabs'

interface DirectorySearch {
  query: string
  studentId?: string
  courseId?: string
}

interface SaveCommand {
  enrollment: AdminStudentCourseEnrollment
  input: UpdateAdminStudentEnrollmentRequest
  draftKey: string
}

function errorMessage(error: Error): string {
  return error instanceof ApiResponseError
    ? error.message
    : 'Проверьте соединение и повторите попытку.'
}

function fullName(student: AdminStudentDirectoryEntry): string {
  return [student.surname, student.name, student.middleName].filter(Boolean).join(' ')
}

function courseGroups(
  course: AdminCourse | undefined,
  enrollment: AdminStudentCourseEnrollment,
): AdminEnrollmentGroup[] {
  const groups = new Map(
    (course?.groups ?? []).map((group) => [
      group.groupId,
      {
        groupId: group.groupId,
        code: group.shortCode,
        name: group.name,
        status: group.status,
        colorKey: group.colorKey ?? 'neutral',
        sortOrder: group.sortOrder,
      } satisfies AdminEnrollmentGroup,
    ]),
  )
  for (const group of enrollment.allowedGroups) groups.set(group.groupId, group)
  return [...groups.values()].sort(
    (left, right) => left.sortOrder - right.sortOrder || left.code.localeCompare(right.code, 'ru'),
  )
}

function EnrollmentEditor({
  accountId,
  allGroups,
  canEditGroup,
  canManageEnrollment,
  enrollment,
  saving,
  storageNamespace,
  onSave,
}: {
  accountId: string
  allGroups: AdminEnrollmentGroup[]
  canEditGroup: (groupId: string) => boolean
  canManageEnrollment: boolean
  enrollment: AdminStudentCourseEnrollment
  saving: boolean
  storageNamespace: string
  onSave: (command: SaveCommand) => void
}) {
  const fallback = {
    schemaVersion: 1 as const,
    activeGroupId: enrollment.activeGroupId,
    allowedGroupIds: enrollment.allowedGroups.map((group) => group.groupId),
    attendanceMode: enrollment.attendanceMode,
    status: enrollment.status,
  }
  const draftKey = enrollmentDraftKey(
    storageNamespace,
    accountId,
    enrollment.enrollmentId,
    enrollment.version,
  )
  const [draft, setDraft] = useState(() =>
    readEnrollmentDraft(globalThis.localStorage, draftKey, fallback),
  )
  const [storageAvailable, setStorageAvailable] = useState(true)
  const changed = JSON.stringify(draft) !== JSON.stringify(fallback)

  function update(next: UpdateAdminStudentEnrollmentRequest) {
    setDraft(next)
    setStorageAvailable(writeEnrollmentDraft(globalThis.localStorage, draftKey, next))
  }

  function toggleGroup(groupId: string, checked: boolean) {
    if (!checked && groupId === draft.activeGroupId) return
    const allowed = new Set(draft.allowedGroupIds)
    if (checked) allowed.add(groupId)
    else allowed.delete(groupId)
    update({ ...draft, allowedGroupIds: [...allowed] })
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    onSave({ enrollment, input: draft, draftKey })
  }

  return (
    <form className="space-y-4" onSubmit={submit}>
      <div className="grid gap-3 md:grid-cols-3">
        <Label className="grid gap-1">
          Активная группа
          <select
            className="min-h-10 rounded-md border border-input bg-surface px-3 text-small"
            disabled={saving}
            onChange={(event) => update({ ...draft, activeGroupId: event.target.value })}
            value={draft.activeGroupId}
          >
            {allGroups
              .filter(
                (group) =>
                  draft.allowedGroupIds.includes(group.groupId) &&
                  group.status !== 'archived' &&
                  canEditGroup(group.groupId),
              )
              .map((group) => (
                <option key={group.groupId} value={group.groupId}>
                  {group.code} · {group.name}
                </option>
              ))}
          </select>
        </Label>
        <Label className="grid gap-1">
          Формат занятий
          <select
            className="min-h-10 rounded-md border border-input bg-surface px-3 text-small"
            disabled={saving || !canManageEnrollment}
            onChange={(event) =>
              update({
                ...draft,
                attendanceMode: event.target.value as 'online' | 'in_person',
              })
            }
            value={draft.attendanceMode}
          >
            <option value="online">Онлайн</option>
            <option value="in_person">Очно</option>
          </select>
        </Label>
        <Label className="grid gap-1">
          Состояние записи
          <select
            className="min-h-10 rounded-md border border-input bg-surface px-3 text-small"
            disabled={saving || !canManageEnrollment}
            onChange={(event) =>
              update({
                ...draft,
                status: event.target.value as 'active' | 'paused' | 'archived',
              })
            }
            value={draft.status}
          >
            <option value="active">Активна</option>
            <option value="paused">Приостановлена</option>
            <option value="archived">В архиве</option>
          </select>
        </Label>
      </div>

      <fieldset className="space-y-2">
        <legend className="text-small font-medium">Доступные группы</legend>
        <div className="flex flex-wrap gap-x-5 gap-y-2">
          {allGroups.map((group) => {
            const active = group.groupId === draft.activeGroupId
            return (
              <Label className="flex items-center gap-2 text-small" key={group.groupId}>
                <Checkbox
                  checked={draft.allowedGroupIds.includes(group.groupId)}
                  disabled={saving || !canManageEnrollment || active}
                  onCheckedChange={(checked) => toggleGroup(group.groupId, checked === true)}
                />
                <span>
                  {group.code} · {group.name}
                  {group.status === 'archived' ? ' (архив)' : ''}
                </span>
              </Label>
            )
          })}
        </div>
        <p className="text-caption text-muted-foreground">
          Активную группу нельзя убрать из доступных. Сначала выберите другую активную группу.
        </p>
      </fieldset>

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
        {saving ? 'Сохраняем…' : 'Сохранить изменения'}
      </Button>
    </form>
  )
}

export function StudentDirectoryView({
  accountId,
  canEditGroup = () => true,
  canManageEnrollment = true,
  courses,
  search,
  saving = false,
  accountSaving = false,
  batchAccountSaving = false,
  familySaving = false,
  showPrivateAccounts = true,
  storageNamespace,
  students,
  onSave,
  onAccountChange,
  onCreateStudentAccounts,
  onCreateStudentAccount,
  onFamilyChange,
  onSearchChange,
}: {
  accountId: string
  canEditGroup?: (courseId: string, groupId: string) => boolean
  canManageEnrollment?: boolean
  courses: AdminCourse[]
  search: DirectorySearch
  saving?: boolean
  accountSaving?: boolean
  batchAccountSaving?: boolean
  familySaving?: boolean
  showPrivateAccounts?: boolean
  storageNamespace: string
  students: AdminStudentDirectoryEntry[]
  onSave: (command: SaveCommand) => void
  onAccountChange?: (command: AccountLifecycleCommand) => Promise<void>
  onCreateStudentAccounts?: (
    commands: StudentAccountBatchCommand[],
  ) => Promise<StudentAccountBatchResult>
  onCreateStudentAccount?: (studentId: string, input: CreateStudentAccountRequest) => Promise<void>
  onFamilyChange?: (command: FamilyAccountCommand) => Promise<void>
  onSearchChange: (search: DirectorySearch) => void
}) {
  const matches = filterStudents(students, search.query)
  const selectedStudent =
    matches.find((student) => student.studentId === search.studentId) ?? matches[0]
  const selectedEnrollment =
    selectedStudent?.enrollments.find(
      (enrollment) => enrollment.course.courseId === search.courseId,
    ) ?? selectedStudent?.enrollments[0]
  const selectedCourse = courses.find(
    (course) => course.courseId === selectedEnrollment?.course.courseId,
  )
  const studentList = useRef<HTMLDivElement>(null)
  // React Compiler is intentionally disabled; this is TanStack Virtual's supported hook.
  // eslint-disable-next-line react-hooks/incompatible-library
  const studentRows = useVirtualizer({
    count: matches.length,
    estimateSize: () => 60,
    getScrollElement: () => studentList.current,
    overscan: 8,
  })

  return (
    <div className="space-y-4">
      {showPrivateAccounts && onCreateStudentAccounts ? (
        <StudentAccountBatchPanel
          onCreate={onCreateStudentAccounts}
          pending={batchAccountSaving}
          staffAccountId={accountId}
          storageNamespace={storageNamespace}
          students={students}
        />
      ) : null}
      <div className="grid min-h-[34rem] gap-4 lg:grid-cols-[20rem_minmax(0,1fr)]">
        <Card className="min-w-0">
          <CardHeader className="gap-3">
            <CardTitle>Школьники</CardTitle>
            <Label className="grid gap-1 text-small">
              Поиск по имени
              <Input
                onChange={(event) => onSearchChange({ query: event.target.value })}
                placeholder="Фамилия, имя или часть с опечаткой"
                type="search"
                value={search.query}
              />
            </Label>
            <p className="text-caption text-muted-foreground">Найдено: {matches.length}</p>
          </CardHeader>
          <CardContent
            aria-label="Список школьников"
            className="max-h-[48rem] overflow-y-auto px-2 pb-2"
            ref={studentList}
            role="region"
          >
            {matches.length === 0 ? (
              <p className="p-3 text-small text-muted-foreground">Никого не нашли.</p>
            ) : (
              <ol className="relative w-full" style={{ height: `${studentRows.getTotalSize()}px` }}>
                {studentRows.getVirtualItems().map((virtualRow) => {
                  const student = matches[virtualRow.index]!
                  const selected = selectedStudent?.studentId === student.studentId
                  return (
                    <li
                      className="absolute left-0 top-0 w-full pr-1"
                      key={student.studentId}
                      style={{
                        height: `${virtualRow.size}px`,
                        transform: `translateY(${virtualRow.start}px)`,
                      }}
                    >
                      <button
                        aria-current={selected ? 'true' : undefined}
                        className="h-[3.5rem] w-full rounded-md border border-transparent px-3 py-2 text-left hover:bg-muted aria-current:border-border aria-current:bg-muted"
                        onClick={() =>
                          onSearchChange({ query: search.query, studentId: student.studentId })
                        }
                        type="button"
                      >
                        <span className="block text-small font-medium">{fullName(student)}</span>
                        <span className="mt-1 flex flex-wrap gap-1 text-caption text-muted-foreground">
                          <span>
                            {student.grade === null ? 'класс —' : `${student.grade} класс`}
                          </span>
                          <span>·</span>
                          <span>
                            {student.strength === null ? 'сила —' : `сила ${student.strength}`}
                          </span>
                          {student.enrollments.length === 0 ? <span>· нет курса</span> : null}
                        </span>
                      </button>
                    </li>
                  )
                })}
              </ol>
            )}
          </CardContent>
        </Card>

        {selectedStudent ? (
          <div className="min-w-0 space-y-4">
            <Card>
              <CardHeader>
                <div className="flex flex-wrap items-center gap-2">
                  <CardTitle>{fullName(selectedStudent)}</CardTitle>
                  {showPrivateAccounts ? (
                    <Badge
                      variant={
                        selectedStudent.webAccount?.status === 'active' ? 'success' : 'warning'
                      }
                    >
                      {selectedStudent.webAccount === null
                        ? 'Web-вход не создан'
                        : selectedStudent.webAccount.status === 'active'
                          ? 'Web-вход активен'
                          : 'Web-вход отключён'}
                    </Badge>
                  ) : null}
                </div>
              </CardHeader>
              <CardContent className="grid gap-3 text-small sm:grid-cols-2 xl:grid-cols-4">
                <div>
                  <p className="text-caption text-muted-foreground">Класс</p>
                  <p>{selectedStudent.grade ?? '—'}</p>
                </div>
                <div>
                  <p className="text-caption text-muted-foreground">Дата рождения</p>
                  <p>{selectedStudent.birthday ?? '—'}</p>
                </div>
                <div>
                  <p className="text-caption text-muted-foreground">Сила</p>
                  <p>{selectedStudent.strength ?? '—'}</p>
                </div>
                {showPrivateAccounts ? (
                  <>
                    <div>
                      <p className="text-caption text-muted-foreground">Логин</p>
                      <p>{selectedStudent.webAccount?.username ?? '—'}</p>
                    </div>
                    <div className="sm:col-span-2 xl:col-span-4">
                      <p className="text-caption text-muted-foreground">Семейные аккаунты</p>
                      <p>
                        {selectedStudent.familyAccounts.length === 0
                          ? '—'
                          : selectedStudent.familyAccounts
                              .map(
                                (account) =>
                                  `${account.displayName} · ${account.username} · ${account.relationshipLabel}`,
                              )
                              .join(', ')}
                      </p>
                    </div>
                  </>
                ) : null}
              </CardContent>
            </Card>

            {showPrivateAccounts && onAccountChange ? (
              <Card>
                <CardHeader>
                  <CardTitle>Доступ в кабинеты</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  {selectedStudent.webAccount ? (
                    <StudentAccountControls
                      account={selectedStudent.webAccount}
                      audience="student"
                      key={`${selectedStudent.webAccount.accountId}:${selectedStudent.webAccount.credentialVersion}`}
                      onChange={onAccountChange}
                      pending={accountSaving}
                    />
                  ) : onCreateStudentAccount ? (
                    <StudentAccountCreator
                      key={`student-account:${selectedStudent.studentId}`}
                      onCreate={onCreateStudentAccount}
                      pending={accountSaving}
                      staffAccountId={accountId}
                      storageNamespace={storageNamespace}
                      studentId={selectedStudent.studentId}
                      usernameSuggestion={selectedStudent.usernameSuggestion}
                    />
                  ) : (
                    <p className="text-small text-muted-foreground">
                      Аккаунт школьника ещё не создан.
                    </p>
                  )}
                  {onFamilyChange ? (
                    <FamilyAccountManager
                      accounts={selectedStudent.familyAccounts}
                      key={`family-accounts:${selectedStudent.studentId}`}
                      onChange={onFamilyChange}
                      pending={familySaving}
                      staffAccountId={accountId}
                      storageNamespace={storageNamespace}
                      studentId={selectedStudent.studentId}
                    />
                  ) : null}
                  {selectedStudent.familyAccounts.map((account) => (
                    <div className="space-y-2" key={account.accountId}>
                      <p className="text-small text-muted-foreground">
                        {account.displayName} · {account.relationshipLabel}
                      </p>
                      <StudentAccountControls
                        account={account}
                        audience="family"
                        key={`${account.accountId}:${account.credentialVersion}`}
                        onChange={onAccountChange}
                        pending={accountSaving}
                      />
                    </div>
                  ))}
                </CardContent>
              </Card>
            ) : null}

            {selectedStudent.enrollments.length === 0 ? (
              <Card>
                <CardContent className="pt-5 text-small text-muted-foreground">
                  Школьник пока не записан ни на один курс.
                </CardContent>
              </Card>
            ) : (
              <Card>
                <CardHeader className="gap-3">
                  <CardTitle>Курс и доступ</CardTitle>
                  {selectedStudent.enrollments.length > 1 ? (
                    <Label className="grid max-w-sm gap-1 text-small">
                      Курс
                      <select
                        className="min-h-10 rounded-md border border-input bg-surface px-3 text-small"
                        onChange={(event) =>
                          onSearchChange({
                            ...search,
                            studentId: selectedStudent.studentId,
                            courseId: event.target.value,
                          })
                        }
                        value={selectedEnrollment?.course.courseId}
                      >
                        {selectedStudent.enrollments.map((enrollment) => (
                          <option key={enrollment.enrollmentId} value={enrollment.course.courseId}>
                            {enrollment.course.name}
                          </option>
                        ))}
                      </select>
                    </Label>
                  ) : (
                    <p className="text-small text-muted-foreground">
                      {selectedEnrollment?.course.name}
                    </p>
                  )}
                </CardHeader>
                <CardContent>
                  {selectedEnrollment ? (
                    <EnrollmentEditor
                      accountId={accountId}
                      allGroups={courseGroups(selectedCourse, selectedEnrollment)}
                      canEditGroup={(groupId) =>
                        canEditGroup(selectedEnrollment.course.courseId, groupId)
                      }
                      canManageEnrollment={canManageEnrollment}
                      enrollment={selectedEnrollment}
                      key={`${selectedEnrollment.enrollmentId}:${selectedEnrollment.version}`}
                      onSave={onSave}
                      saving={saving}
                      storageNamespace={storageNamespace}
                    />
                  ) : null}
                </CardContent>
              </Card>
            )}
          </div>
        ) : null}
      </div>
    </div>
  )
}

/** Staff user/access flow from design-system page 5 and development Phase 10. */
export function StaffStudentDirectoryPage({
  search,
  onSectionChange,
  onSearchChange,
}: {
  search: DirectorySearch
  onSectionChange: (section: UsersSection) => void
  onSearchChange: (search: DirectorySearch) => void
}) {
  const authentication = useAuthentication()
  const principal = useAuthenticatedPrincipal()
  if (principal.audience !== 'staff') throw new Error('Student directory requires Staff auth')
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
  const directory = useAdminStudentEnrollmentsQuery(client, scope)
  const catalog = useAdminCourseCatalogQuery(client, scope, undefined, isAdmin)
  const queryClient = useQueryClient()
  const mutation = useMutation({
    mutationFn: (command: SaveCommand) =>
      client.updateStudentEnrollment(
        command.enrollment.enrollmentId,
        command.enrollment.version,
        command.input,
      ),
    onSuccess: async (_, command) => {
      clearEnrollmentDraft(globalThis.localStorage, command.draftKey)
      await queryClient.invalidateQueries({ queryKey: adminStudentEnrollmentsQueryKey(scope) })
    },
    onError: (error) => authentication.handleApiError(error),
  })
  const accountMutation = useMutation({
    mutationFn: (command: AccountLifecycleCommand) =>
      command.kind === 'status'
        ? client.updateAccountStatus(command.accountId, command.version, command.status)
        : client.replaceAccountCredential(command.accountId, command.version, command.credential),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: adminStudentEnrollmentsQueryKey(scope) })
    },
    onError: (error) => authentication.handleApiError(error),
  })
  const familyMutation = useMutation({
    mutationFn: async (command: FamilyAccountCommand) => {
      if (command.kind === 'create') {
        await client.createFamilyAccount(command.studentId, command.input)
        return
      }
      if (command.kind === 'link') {
        await client.linkFamilyAccount(command.studentId, command.input)
        return
      }
      await client.unlinkFamilyAccount(command.studentId, command.accountId)
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: adminStudentEnrollmentsQueryKey(scope) })
    },
    onError: (error) => authentication.handleApiError(error),
  })
  const createStudentAccountMutation = useMutation({
    mutationFn: ({ studentId, input }: { studentId: string; input: CreateStudentAccountRequest }) =>
      client.createStudentAccount(studentId, input),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: adminStudentEnrollmentsQueryKey(scope) })
    },
    onError: (error) => authentication.handleApiError(error),
  })
  const createStudentAccountsMutation = useMutation({
    mutationFn: async (
      commands: StudentAccountBatchCommand[],
    ): Promise<StudentAccountBatchResult> => {
      const createdStudentIds: string[] = []
      const failures: StudentAccountBatchResult['failures'] = []
      // Phase 10 daily batches deliberately reuse the audited single-account
      // endpoint; the guarded auth-import CLI remains the initial bulk path.
      for (const command of commands) {
        try {
          await client.createStudentAccount(command.studentId, {
            schemaVersion: 1,
            username: command.username,
          })
          createdStudentIds.push(command.studentId)
        } catch (caught) {
          authentication.handleApiError(caught)
          failures.push({
            studentId: command.studentId,
            message: errorMessage(caught instanceof Error ? caught : new Error('unknown error')),
          })
        }
      }
      return { createdStudentIds, failures }
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: adminStudentEnrollmentsQueryKey(scope) })
    },
  })

  if (directory.isPending || (isAdmin && catalog.isPending)) {
    return (
      <PageLayout title="Участники и группы" width="wide">
        <PageStatePanel state="loading" />
      </PageLayout>
    )
  }
  const error = directory.error ?? (isAdmin ? catalog.error : null)
  if (error) {
    return (
      <PageLayout title="Участники и группы" width="wide">
        <PageStatePanel
          actionLabel="Повторить"
          onAction={() =>
            void Promise.all([directory.refetch(), ...(isAdmin ? [catalog.refetch()] : [])])
          }
          state={error instanceof ApiResponseError && error.status === 403 ? 'forbidden' : 'error'}
        />
      </PageLayout>
    )
  }
  if (!directory.data || (isAdmin && !catalog.data)) {
    return (
      <PageLayout title="Участники и группы" width="wide">
        <PageStatePanel state="error" />
      </PageLayout>
    )
  }

  return (
    <PageLayout
      description="Поиск школьника, его курсы, активные и доступные группы и формат занятий."
      eyebrow={isAdmin ? 'Admin' : 'Teacher'}
      title="Участники и группы"
      width="wide"
    >
      <div className="space-y-4">
        <UsersSectionTabs onChange={onSectionChange} section="students" showTeachers={isAdmin} />
        {!isAdmin ? (
          <Alert>
            <AlertContent>
              <AlertTitle>Показаны только ваши группы</AlertTitle>
              <AlertDescription>
                Вы можете сменить активную группу школьника в пределах выданного доступа. Остальные
                поля изменяет администратор.
              </AlertDescription>
            </AlertContent>
          </Alert>
        ) : null}
        {mutation.error ||
        accountMutation.error ||
        familyMutation.error ||
        createStudentAccountsMutation.error ||
        createStudentAccountMutation.error ? (
          <Alert role="alert" tone="danger">
            <AlertContent>
              <AlertTitle>Изменение не сохранено</AlertTitle>
              <AlertDescription>
                {errorMessage(
                  (mutation.error ??
                    accountMutation.error ??
                    familyMutation.error ??
                    createStudentAccountsMutation.error ??
                    createStudentAccountMutation.error)!,
                )}
              </AlertDescription>
            </AlertContent>
          </Alert>
        ) : null}
        <StudentDirectoryView
          accountId={principal.accountId}
          canEditGroup={(courseId, groupId) =>
            isAdmin ||
            principal.scopes.some(
              (item) =>
                item.courseId === courseId && (item.groupId === null || item.groupId === groupId),
            )
          }
          canManageEnrollment={isAdmin}
          accountSaving={
            accountMutation.isPending ||
            createStudentAccountMutation.isPending ||
            createStudentAccountsMutation.isPending
          }
          batchAccountSaving={createStudentAccountsMutation.isPending}
          courses={catalog.data?.courses ?? []}
          familySaving={familyMutation.isPending}
          onAccountChange={async (command) => {
            await accountMutation.mutateAsync(command)
          }}
          onFamilyChange={async (command) => {
            await familyMutation.mutateAsync(command)
          }}
          onCreateStudentAccount={async (studentId, input) => {
            await createStudentAccountMutation.mutateAsync({ studentId, input })
          }}
          onCreateStudentAccounts={async (commands) =>
            createStudentAccountsMutation.mutateAsync(commands)
          }
          onSave={(command) => mutation.mutate(command)}
          onSearchChange={onSearchChange}
          saving={mutation.isPending}
          search={search}
          storageNamespace={createBrowserStorageNamespace(authentication.client.runtime)}
          students={directory.data.students}
          showPrivateAccounts={isAdmin}
        />
      </div>
    </PageLayout>
  )
}
