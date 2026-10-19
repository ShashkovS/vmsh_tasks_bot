import { t } from '@lingui/core/macro'
import { Trans } from '@lingui/react/macro'
import { useMemo, useState } from 'react'

import {
  ApiResponseError,
  type AdminCourse,
  type CreateStaffMemberBatchRequest,
  type CreateStaffMemberBatchResponse,
  type StaffAccessMember,
  type StaffScopeSelection,
} from '@vmsh/contracts'
import {
  Alert,
  AlertContent,
  AlertDescription,
  AlertTitle,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Checkbox,
  Label,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
  Textarea,
} from '@vmsh/ui'

import {
  parseTeacherBatchTsv,
  teacherBatchDraftKey,
  TeacherBatchTsvError,
  type TeacherBatchRow,
} from './teacher-batch-tsv'

interface TeacherBatchDraft {
  source: string
  scopes: StaffScopeSelection[]
}

function readDraft(key: string): TeacherBatchDraft {
  try {
    const value = JSON.parse(globalThis.localStorage.getItem(key) ?? 'null') as unknown
    if (
      typeof value === 'object' &&
      value !== null &&
      'source' in value &&
      typeof value.source === 'string' &&
      'scopes' in value &&
      Array.isArray(value.scopes)
    ) {
      return { source: value.source, scopes: value.scopes as StaffScopeSelection[] }
    }
  } catch {
    // A malformed local draft is disposable; server data is unaffected.
  }
  return { source: '', scopes: [] }
}

function writeDraft(key: string, draft: TeacherBatchDraft): boolean {
  try {
    globalThis.localStorage.setItem(key, JSON.stringify(draft))
    return true
  } catch {
    return false
  }
}

function normalizedUsername(value: string): string {
  return value.normalize('NFKC').toLocaleLowerCase('ru')
}

function scopeKey(scope: StaffScopeSelection): string {
  return `${scope.courseId}\0${scope.groupId ?? ''}`
}

function message(error: unknown): string {
  if (error instanceof TeacherBatchTsvError || error instanceof ApiResponseError) {
    return error.message
  }
  return t`Не удалось создать преподавателей. Проверьте соединение и повторите попытку.`
}

export function TeacherBatchPanel({
  accountId,
  courses,
  members,
  storageNamespace,
  onApply,
}: {
  accountId: string
  courses: AdminCourse[]
  members: StaffAccessMember[]
  storageNamespace: string
  onApply: (input: CreateStaffMemberBatchRequest) => Promise<CreateStaffMemberBatchResponse>
}) {
  const draftKey = teacherBatchDraftKey(storageNamespace, accountId)
  const initial = useMemo(() => readDraft(draftKey), [draftKey])
  const [source, setSource] = useState(initial.source)
  const [scopes, setScopes] = useState(initial.scopes)
  const [rows, setRows] = useState<TeacherBatchRow[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [receipt, setReceipt] = useState<CreateStaffMemberBatchResponse | null>(null)
  const [saving, setSaving] = useState(false)
  const [storageAvailable, setStorageAvailable] = useState(true)
  const existingUsernames = useMemo(
    () =>
      new Set(
        members
          .map((member) => member.account?.username)
          .filter((username): username is string => Boolean(username))
          .map(normalizedUsername),
      ),
    [members],
  )
  const conflicts = rows?.filter((row) => existingUsernames.has(normalizedUsername(row.username)))

  function persist(nextSource: string, nextScopes: StaffScopeSelection[]) {
    setStorageAvailable(writeDraft(draftKey, { source: nextSource, scopes: nextScopes }))
  }

  function changeSource(next: string) {
    setSource(next)
    setRows(null)
    setError(null)
    setReceipt(null)
    persist(next, scopes)
  }

  function changeScopes(next: StaffScopeSelection[]) {
    setScopes(next)
    setError(null)
    setReceipt(null)
    persist(source, next)
  }

  function toggleCourse(courseId: string, checked: boolean) {
    const otherCourses = scopes.filter((scope) => scope.courseId !== courseId)
    changeScopes(checked ? [...otherCourses, { courseId, groupId: null }] : otherCourses)
  }

  function toggleGroup(courseId: string, groupId: string, checked: boolean) {
    const withoutCourseWide = scopes.filter(
      (scope) => !(scope.courseId === courseId && scope.groupId === null),
    )
    const key = scopeKey({ courseId, groupId })
    const withoutGroup = withoutCourseWide.filter((scope) => scopeKey(scope) !== key)
    changeScopes(checked ? [...withoutGroup, { courseId, groupId }] : withoutGroup)
  }

  function preview() {
    setError(null)
    setReceipt(null)
    try {
      setRows(parseTeacherBatchTsv(source))
    } catch (caught) {
      setRows(null)
      setError(message(caught))
    }
  }

  async function apply() {
    if (!rows || rows.length === 0 || scopes.length === 0 || (conflicts?.length ?? 0) > 0) return
    setSaving(true)
    setError(null)
    try {
      const next = await onApply({ schemaVersion: 1, rows, scopes })
      setReceipt(next)
      setSource('')
      setRows(null)
      persist('', scopes)
    } catch (caught) {
      setError(message(caught))
    } finally {
      setSaving(false)
    }
  }

  return (
    <Card>
      <CardHeader className="gap-1">
        <CardTitle>
          <Trans>Пакетная загрузка преподавателей</Trans>
        </CardTitle>
        <p className="text-small text-muted-foreground">
          <Trans>
            Одинаковые доступы будут назначены всем строкам этой пачки. Для другого набора доступов
            загрузите следующую пачку.
          </Trans>
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        <Label className="grid gap-1 text-small">
          <Trans>Вставьте преподавателей из таблицы</Trans>
          <Textarea
            className="min-h-36 font-mono text-caption"
            onChange={(event) => changeSource(event.target.value)}
            placeholder={t`Фамилия · Имя · Отчество · Логин · Временный пароль`}
            spellCheck={false}
            value={source}
          />
        </Label>
        <p className="text-caption text-muted-foreground">
          <Trans>
            Ровно пять столбцов, разделённых табуляцией. Отчество можно оставить пустым. Пароль не
            показывается в предпросмотре.
          </Trans>
        </p>

        <fieldset className="space-y-2">
          <legend className="text-small font-medium">
            <Trans>Общие доступы пачки</Trans>
          </legend>
          <div className="grid gap-2 lg:grid-cols-2">
            {courses
              .filter((course) => course.status === 'active')
              .map((course) => {
                const wholeCourse = scopes.some(
                  (scope) => scope.courseId === course.courseId && scope.groupId === null,
                )
                return (
                  <div className="rounded-md border border-border p-3" key={course.courseId}>
                    <Label className="flex items-center gap-2 text-small font-medium">
                      <Checkbox
                        checked={wholeCourse}
                        onCheckedChange={(checked) =>
                          toggleCourse(course.courseId, checked === true)
                        }
                      />
                      <Trans>{course.name} · весь курс</Trans>
                    </Label>
                    <div className="mt-2 flex flex-wrap gap-x-4 gap-y-2">
                      {course.groups
                        .filter((group) => group.status === 'active')
                        .map((group) => (
                          <Label className="flex items-center gap-2 text-small" key={group.groupId}>
                            <Checkbox
                              checked={
                                wholeCourse ||
                                scopes.some(
                                  (scope) =>
                                    scope.courseId === course.courseId &&
                                    scope.groupId === group.groupId,
                                )
                              }
                              disabled={wholeCourse}
                              onCheckedChange={(checked) =>
                                toggleGroup(course.courseId, group.groupId, checked === true)
                              }
                            />
                            {group.shortCode} · {group.name}
                          </Label>
                        ))}
                    </div>
                  </div>
                )
              })}
          </div>
        </fieldset>

        <div className="flex flex-wrap gap-2">
          <Button disabled={!source.trim() || saving} onClick={preview} type="button">
            <Trans>Проверить таблицу</Trans>
          </Button>
          <Button
            disabled={
              saving || !rows?.length || scopes.length === 0 || (conflicts?.length ?? 0) > 0
            }
            onClick={() => void apply()}
            type="button"
            variant="outline"
          >
            {saving ? t`Создаём…` : t`Создать преподавателей · ${rows?.length ?? 0}`}
          </Button>
        </div>

        {!storageAvailable ? (
          <p className="text-small text-status-error" role="alert">
            <Trans>Черновик не сохраняется в этом браузере. Не закрывайте вкладку.</Trans>
          </p>
        ) : (
          <p className="text-caption text-muted-foreground" role="status">
            <Trans>
              Таблица и выбранные доступы сохраняются только в этом браузере до успешного создания.
            </Trans>
          </p>
        )}
        {scopes.length === 0 ? (
          <p className="text-small text-status-warning" role="status">
            <Trans>Выберите хотя бы один курс или группу.</Trans>
          </p>
        ) : null}
        {conflicts?.length ? (
          <Alert tone="danger">
            <AlertContent>
              <AlertTitle>
                <Trans>Логины уже используются</Trans>
              </AlertTitle>
              <AlertDescription>{conflicts.map((row) => row.username).join(', ')}</AlertDescription>
            </AlertContent>
          </Alert>
        ) : null}
        {error ? (
          <Alert role="alert" tone="danger">
            <AlertContent>
              <AlertTitle>
                <Trans>Не удалось продолжить</Trans>
              </AlertTitle>
              <AlertDescription>{error}</AlertDescription>
            </AlertContent>
          </Alert>
        ) : null}
        {receipt ? (
          <Alert tone="success">
            <AlertContent>
              <AlertTitle>
                <Trans>Преподаватели созданы</Trans>
              </AlertTitle>
              <AlertDescription>
                <Trans>Создано: {receipt.counts.created}.</Trans>
              </AlertDescription>
            </AlertContent>
          </Alert>
        ) : null}

        {rows ? (
          <div className="max-h-80 overflow-auto rounded-md border border-border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>
                    <Trans>ФИО</Trans>
                  </TableHead>
                  <TableHead>
                    <Trans>Логин</Trans>
                  </TableHead>
                  <TableHead>
                    <Trans>Результат</Trans>
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.slice(0, 100).map((row) => {
                  const conflict = existingUsernames.has(normalizedUsername(row.username))
                  return (
                    <TableRow key={row.username}>
                      <TableCell>
                        {[row.surname, row.name, row.middleName].filter(Boolean).join(' ')}
                      </TableCell>
                      <TableCell className="font-mono text-caption">{row.username}</TableCell>
                      <TableCell>{conflict ? t`Логин занят` : t`Готово`}</TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          </div>
        ) : null}
        {rows && rows.length > 100 ? (
          <p className="text-caption text-muted-foreground">
            <Trans>Показаны первые 100 из {rows.length}; будут созданы все строки.</Trans>
          </p>
        ) : null}
      </CardContent>
    </Card>
  )
}
