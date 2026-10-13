import { t } from '@lingui/core/macro'
import { Trans } from '@lingui/react/macro'
import { useMemo, useState } from 'react'

import {
  PageLayout,
  PageStatePanel,
  createAdminCourseClient,
  useAuthenticatedPrincipal,
  useAuthentication,
} from '@vmsh/app-shell'
import {
  ApiResponseError,
  createBrowserStorageNamespace,
  type AccountProvisioningPreviewResponse,
  type AccountProvisioningReceipt,
  type CourseEnrollmentProvisioningPreviewResponse,
  type CourseEnrollmentProvisioningReceipt,
  type CourseEnrollmentProvisioningRow,
  type FamilyProvisioningRow,
  type StudentProvisioningRow,
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
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
  Textarea,
} from '@vmsh/ui'

import {
  ProvisioningTsvError,
  parseCourseEnrollmentProvisioningTsv,
  parseFamilyProvisioningTsv,
  parseStudentProvisioningTsv,
  provisioningDraftKey,
  serializeFamilyProvisioningTsv,
  serializeStudentProvisioningTsv,
} from './account-provisioning-tsv'
import { applyProvisioningInChunks } from './account-provisioning-batch'
import { UsersSectionTabs, type UsersSection } from './users-section-tabs'

const diagnosticLabels: Record<string, string> = {
  get invalid_student_row() {
    return t`неверное число или название столбцов`
  },
  get invalid_family_row() {
    return t`неверное число или название столбцов`
  },
  get invalid_enrollment_row() {
    return t`неверное число или название столбцов`
  },
  get invalid_surname() {
    return t`проверьте фамилию`
  },
  get invalid_name() {
    return t`проверьте имя`
  },
  get invalid_patronymic() {
    return t`проверьте отчество`
  },
  get invalid_birth_date() {
    return t`проверьте дату рождения`
  },
  get invalid_grade() {
    return t`класс должен быть от 1 до 11`
  },
  get invalid_login() {
    return t`проверьте логин`
  },
  get invalid_password() {
    return t`проверьте пароль`
  },
  get invalid_emails() {
    return t`проверьте список email`
  },
  get invalid_child_logins() {
    return t`проверьте логины детей`
  },
  get child_login_not_found() {
    return t`школьник с таким логином не найден`
  },
  get student_token_conflict() {
    return t`такой Telegram-токен уже используется`
  },
  get login_suffix_exhausted() {
    return t`не удалось подобрать свободный логин`
  },
  get account_conflict() {
    return t`данные изменились после предпросмотра`
  },
  get account_already_imported() {
    return t`этот родитель уже был импортирован с теми же данными`
  },
  get family_login_duplicate() {
    return t`родитель с таким логином уже есть`
  },
  get family_email_duplicate() {
    return t`родитель с таким email уже есть`
  },
  get family_login_email_duplicate() {
    return t`родитель с таким логином и email уже есть`
  },
  get invalid_row() {
    return t`строка не прошла проверку`
  },
  get invalid_course() {
    return t`проверьте код курса`
  },
  get invalid_allowed_groups() {
    return t`проверьте список доступных групп`
  },
  get student_login_not_found() {
    return t`школьник с таким логином не найден`
  },
  get course_not_found() {
    return t`курс с таким кодом не найден`
  },
  get course_archived() {
    return t`курс находится в архиве`
  },
  get group_not_found() {
    return t`одна из групп не найдена в этом курсе`
  },
  get group_archived() {
    return t`одна из групп находится в архиве`
  },
  get duplicate_enrollment_row() {
    return t`зачисление повторено в этой таблице`
  },
  get enrollment_exists() {
    return t`школьник уже зачислен на этот курс`
  },
  get row_conflict() {
    return t`строка конфликтует с актуальными данными`
  },
}

function readDraft(key: string) {
  try {
    return globalThis.localStorage.getItem(key) ?? ''
  } catch {
    return ''
  }
}

function saveDraft(key: string, value: string) {
  try {
    if (value) globalThis.localStorage.setItem(key, value)
    else globalThis.localStorage.removeItem(key)
    return true
  } catch {
    return false
  }
}

function errorText(error: unknown) {
  if (error instanceof ProvisioningTsvError || error instanceof ApiResponseError) {
    return error.message
  }
  return t`Сервер не подтвердил операцию. Уже завершённые части пакета сохранены; обновите предпросмотр перед повтором.`
}

function provisioningRowIdentity(
  row: StudentProvisioningRow | FamilyProvisioningRow | undefined,
): string {
  if (!row) return '—'
  return 'surname' in row
    ? `${row.surname} ${row.name} · ${row.login}`
    : `${row.name} · ${row.login}`
}

const familyDuplicateCodes = new Set([
  'account_already_imported',
  'family_login_duplicate',
  'family_email_duplicate',
  'family_login_email_duplicate',
])

function isFamilyDuplicate(code: string): boolean {
  return familyDuplicateCodes.has(code)
}

function ProvisioningPanel<Row extends StudentProvisioningRow | FamilyProvisioningRow>({
  audience,
  columns,
  description,
  draftKey,
  parse,
  serialize,
  previewRequest,
  applyRequest,
}: {
  audience: 'student' | 'family'
  columns: string
  description: string
  draftKey: string
  parse: (source: string) => Row[]
  serialize: (rows: Row[]) => string
  previewRequest: (rows: Row[]) => Promise<AccountProvisioningPreviewResponse>
  applyRequest: (
    rows: Row[],
    preview: AccountProvisioningPreviewResponse,
    onProgress?: (processed: number, total: number) => void,
    onChunkCompleted?: (rows: AccountProvisioningReceipt['rows']) => void,
  ) => Promise<AccountProvisioningReceipt>
}) {
  const [source, setSource] = useState(() => readDraft(draftKey))
  const [rows, setRows] = useState<Row[] | null>(null)
  const [preview, setPreview] = useState<AccountProvisioningPreviewResponse | null>(null)
  const [receipt, setReceipt] = useState<AccountProvisioningReceipt | null>(null)
  const [receiptRows, setReceiptRows] = useState<Row[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState<'preview' | 'apply' | null>(null)
  const [applyProgress, setApplyProgress] = useState<{ processed: number; total: number } | null>(
    null,
  )
  const [storageAvailable, setStorageAvailable] = useState(true)
  const title = audience === 'student' ? t`1. Школьники` : t`2. Родители`
  const previewDuplicateCount =
    audience === 'family'
      ? (preview?.rows.filter((row) => row.state === 'invalid' && isFamilyDuplicate(row.code))
          .length ?? 0)
      : 0
  const previewErrorCount = (preview?.counts.invalid ?? 0) - previewDuplicateCount
  const receiptDuplicateCount =
    audience === 'family'
      ? (receipt?.rows.filter((row) => row.state === 'skipped' && isFamilyDuplicate(row.code))
          .length ?? 0)
      : 0
  const receiptErrorCount = (receipt?.counts.skipped ?? 0) - receiptDuplicateCount

  function changeSource(value: string) {
    setSource(value)
    setRows(null)
    setPreview(null)
    setReceipt(null)
    setReceiptRows(null)
    setError(null)
    setStorageAvailable(saveDraft(draftKey, value))
  }

  async function previewRows() {
    setPending('preview')
    setError(null)
    try {
      const parsed = parse(source)
      const next = await previewRequest(parsed)
      setRows(parsed)
      setPreview(next)
      setReceipt(null)
      setReceiptRows(null)
    } catch (caught) {
      setRows(null)
      setPreview(null)
      setError(errorText(caught))
    } finally {
      setPending(null)
    }
  }

  async function applyRows() {
    if (!rows || !preview) return
    setPending('apply')
    setApplyProgress({ processed: 0, total: rows.length })
    setError(null)
    try {
      const appliedRows = rows
      const remainingNumbers = new Set(appliedRows.map((_, index) => index + 1))
      for (const row of preview.rows) {
        if (row.state === 'invalid' && isFamilyDuplicate(row.code)) {
          remainingNumbers.delete(row.rowNumber)
        }
      }
      const next = await applyRequest(
        rows,
        preview,
        (processed, total) => setApplyProgress({ processed, total }),
        (completedRows) => {
          for (const row of completedRows) {
            if (row.state === 'created' || isFamilyDuplicate(row.code)) {
              remainingNumbers.delete(row.rowNumber)
            }
          }
          const remainingSource = serialize(
            appliedRows.filter((_, index) => remainingNumbers.has(index + 1)),
          )
          setSource(remainingSource)
          setStorageAvailable(saveDraft(draftKey, remainingSource))
        },
      )
      setReceipt(next)
      setReceiptRows(appliedRows)
      if (next.counts.created === next.counts.total) {
        setSource('')
        setRows(null)
        setPreview(null)
        setStorageAvailable(saveDraft(draftKey, ''))
      } else {
        const skippedNumbers = new Set(
          next.rows
            .filter((row) => row.state === 'skipped' && !isFamilyDuplicate(row.code))
            .map((row) => row.rowNumber),
        )
        const remainingRows = appliedRows.filter((_, index) => skippedNumbers.has(index + 1))
        const remainingSource = serialize(remainingRows)
        setSource(remainingSource)
        setRows(null)
        setPreview(null)
        setStorageAvailable(saveDraft(draftKey, remainingSource))
      }
    } catch (caught) {
      setError(errorText(caught))
    } finally {
      setPending(null)
      setApplyProgress(null)
    }
  }

  return (
    <Card>
      <CardHeader className="gap-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <CardTitle>{title}</CardTitle>
          {preview ? (
            <div className="flex gap-1">
              <Badge variant="success">
                <Trans>Готовы: {preview.counts.ready}</Trans>
              </Badge>
              {previewDuplicateCount ? (
                <Badge variant="secondary">
                  <Trans>Дубли: {previewDuplicateCount}</Trans>
                </Badge>
              ) : null}
              {previewErrorCount ? (
                <Badge variant="warning">
                  <Trans>Проверить: {previewErrorCount}</Trans>
                </Badge>
              ) : null}
            </div>
          ) : null}
        </div>
        <p className="text-small text-muted-foreground">{description}</p>
      </CardHeader>
      <CardContent className="space-y-3">
        <Label className="grid gap-1 text-small">
          <Trans>Вставьте строки из таблицы</Trans>
          <Textarea
            className="min-h-36 font-mono text-caption"
            onChange={(event) => changeSource(event.target.value)}
            placeholder={columns}
            spellCheck={false}
            value={source}
          />
        </Label>
        <p className="text-caption text-muted-foreground">
          <Trans>
            Порядок столбцов: {columns}. Пустые необязательные ячейки оставляйте пустыми;
            разделители между столбцами должны оставаться табуляцией.
          </Trans>
        </p>
        {!storageAvailable ? (
          <p className="text-small text-status-error" role="alert">
            <Trans>Черновик не сохраняется в этом браузере. Не закрывайте вкладку.</Trans>
          </p>
        ) : (
          <p className="text-caption text-muted-foreground" role="status">
            <Trans>
              Вставленный текст сохраняется только в этом браузере до успешного создания аккаунтов.
            </Trans>
          </p>
        )}

        <div className="flex flex-wrap gap-2">
          <Button
            disabled={!source.trim() || pending !== null}
            onClick={() => void previewRows()}
            type="button"
          >
            {pending === 'preview' ? t`Проверяем…` : t`Проверить таблицу`}
          </Button>
          <Button
            disabled={!preview?.counts.ready || pending !== null}
            onClick={() => void applyRows()}
            type="button"
            variant="outline"
          >
            {pending === 'apply'
              ? t`Создаём… ${applyProgress?.processed ?? 0}/${applyProgress?.total ?? rows?.length ?? 0}`
              : t`Создать готовые · ${preview?.counts.ready ?? 0}`}
          </Button>
        </div>

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

        {preview ? (
          <>
            {previewDuplicateCount ? (
              <p className="text-small font-medium text-muted-foreground">
                <Trans>
                  Дубли уже существующих логинов или email будут проигнорированы:{' '}
                  {previewDuplicateCount}.
                </Trans>
              </p>
            ) : null}
            {previewErrorCount ? (
              <p className="text-small font-medium text-status-warning">
                <Trans>Эти строки не будут загружены, пока ошибки не исправлены:</Trans>
              </p>
            ) : null}
            <div className="max-h-80 overflow-auto rounded-md border border-border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-16">
                      <Trans>Строка</Trans>
                    </TableHead>
                    <TableHead>
                      <Trans>Родитель или школьник</Trans>
                    </TableHead>
                    <TableHead>
                      <Trans>Итоговый логин</Trans>
                    </TableHead>
                    <TableHead>
                      <Trans>Результат</Trans>
                    </TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {(preview.counts.invalid
                    ? preview.rows.filter((row) => row.state === 'invalid')
                    : preview.rows.slice(0, 100)
                  ).map((row) => (
                    <TableRow key={row.rowNumber}>
                      <TableCell>{row.rowNumber}</TableCell>
                      <TableCell>{provisioningRowIdentity(rows?.[row.rowNumber - 1])}</TableCell>
                      <TableCell className="font-mono text-caption">
                        {row.resolvedLogin ?? '—'}
                        {row.state === 'ready' && row.loginAdjusted ? t` · изменён` : ''}
                      </TableCell>
                      <TableCell>
                        {row.state === 'ready'
                          ? t`Готово`
                          : (diagnosticLabels[row.code] ?? row.code)}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </>
        ) : null}
        {preview && !preview.counts.invalid && preview.rows.length > 100 ? (
          <p className="text-caption text-muted-foreground">
            <Trans>
              Показаны первые 100 из {preview.rows.length}; итоговые счётчики учитывают все строки.
            </Trans>
          </p>
        ) : null}
        {receipt ? (
          <Alert tone={receiptErrorCount ? 'warning' : 'success'}>
            <AlertContent>
              <AlertTitle>
                <Trans>Пакет обработан</Trans>
              </AlertTitle>
              <AlertDescription>
                <Trans>
                  Создано: {receipt.counts.created}. Дубликатов проигнорировано:{' '}
                  {receiptDuplicateCount}. Не создано из-за ошибок: {receiptErrorCount}.
                </Trans>
                {receiptErrorCount
                  ? t` В поле выше оставлены только строки, которые нужно исправить.`
                  : ''}
              </AlertDescription>
            </AlertContent>
          </Alert>
        ) : null}
        {receipt?.counts.skipped && receiptRows ? (
          <div className="space-y-2">
            <p className="text-small font-medium">
              <Trans>Пропущены</Trans>
            </p>
            <div className="max-h-80 overflow-auto rounded-md border border-border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-16">
                      <Trans>Строка</Trans>
                    </TableHead>
                    <TableHead>
                      <Trans>Родитель или школьник</Trans>
                    </TableHead>
                    <TableHead>
                      <Trans>Причина</Trans>
                    </TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {receipt.rows
                    .filter((row) => row.state === 'skipped')
                    .map((row) => {
                      const identity = provisioningRowIdentity(receiptRows[row.rowNumber - 1])
                      return (
                        <TableRow key={row.rowNumber}>
                          <TableCell>{row.rowNumber}</TableCell>
                          <TableCell>{identity}</TableCell>
                          <TableCell>{diagnosticLabels[row.code] ?? row.code}</TableCell>
                        </TableRow>
                      )
                    })}
                </TableBody>
              </Table>
            </div>
          </div>
        ) : null}
      </CardContent>
    </Card>
  )
}

function CourseEnrollmentProvisioningPanel({
  draftKey,
  previewRequest,
  applyRequest,
}: {
  draftKey: string
  previewRequest: (
    rows: CourseEnrollmentProvisioningRow[],
  ) => Promise<CourseEnrollmentProvisioningPreviewResponse>
  applyRequest: (
    rows: CourseEnrollmentProvisioningRow[],
    preview: CourseEnrollmentProvisioningPreviewResponse,
  ) => Promise<CourseEnrollmentProvisioningReceipt>
}) {
  const [source, setSource] = useState(() => readDraft(draftKey))
  const [rows, setRows] = useState<CourseEnrollmentProvisioningRow[] | null>(null)
  const [preview, setPreview] = useState<CourseEnrollmentProvisioningPreviewResponse | null>(null)
  const [receipt, setReceipt] = useState<CourseEnrollmentProvisioningReceipt | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState<'preview' | 'apply' | null>(null)
  const [storageAvailable, setStorageAvailable] = useState(true)

  function changeSource(value: string) {
    setSource(value)
    setRows(null)
    setPreview(null)
    setReceipt(null)
    setError(null)
    setStorageAvailable(saveDraft(draftKey, value))
  }

  async function previewRows() {
    setPending('preview')
    setError(null)
    try {
      const parsed = parseCourseEnrollmentProvisioningTsv(source)
      const next = await previewRequest(parsed)
      setRows(parsed)
      setPreview(next)
      setReceipt(null)
    } catch (caught) {
      setRows(null)
      setPreview(null)
      setError(errorText(caught))
    } finally {
      setPending(null)
    }
  }

  async function applyRows() {
    if (!rows || !preview) return
    setPending('apply')
    setError(null)
    try {
      const next = await applyRequest(rows, preview)
      setReceipt(next)
      if (next.counts.created === next.counts.total) {
        setSource('')
        setRows(null)
        setPreview(null)
        setStorageAvailable(saveDraft(draftKey, ''))
      }
    } catch (caught) {
      setError(errorText(caught))
    } finally {
      setPending(null)
    }
  }

  return (
    <Card>
      <CardHeader className="gap-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <CardTitle>
            <Trans>3. Зачисление на курс</Trans>
          </CardTitle>
          {preview ? (
            <div className="flex gap-1">
              <Badge variant="success">
                <Trans>Готовы: {preview.counts.ready}</Trans>
              </Badge>
              {preview.counts.invalid ? (
                <Badge variant="warning">
                  <Trans>Проверить: {preview.counts.invalid}</Trans>
                </Badge>
              ) : null}
            </div>
          ) : null}
        </div>
        <p className="text-small text-muted-foreground">
          <Trans>
            Запускайте отдельно для каждого курса. Активной станет первая доступная группа по её
            порядку, а не первая группа в строке.
          </Trans>
        </p>
      </CardHeader>
      <CardContent className="space-y-3">
        <Label className="grid gap-1 text-small">
          <Trans>Вставьте строки зачисления</Trans>
          <Textarea
            className="min-h-36 font-mono text-caption"
            onChange={(event) => changeSource(event.target.value)}
            placeholder={t`Логин · Код курса · Коды доступных групп через запятую`}
            spellCheck={false}
            value={source}
          />
        </Label>
        <p className="text-caption text-muted-foreground">
          <Trans>
            Порядок столбцов: логин, код курса, доступные группы. Группы можно разделять запятыми
            или точками с запятой.
          </Trans>
        </p>
        {!storageAvailable ? (
          <p className="text-small text-status-error" role="alert">
            <Trans>Черновик не сохраняется в этом браузере. Не закрывайте вкладку.</Trans>
          </p>
        ) : (
          <p className="text-caption text-muted-foreground" role="status">
            <Trans>
              Вставленный текст сохраняется только в этом браузере до успешного зачисления.
            </Trans>
          </p>
        )}
        <div className="flex flex-wrap gap-2">
          <Button
            disabled={!source.trim() || pending !== null}
            onClick={() => void previewRows()}
            type="button"
          >
            {pending === 'preview' ? t`Проверяем…` : t`Проверить зачисление`}
          </Button>
          <Button
            disabled={!preview?.counts.ready || pending !== null}
            onClick={() => void applyRows()}
            type="button"
            variant="outline"
          >
            {pending === 'apply'
              ? t`Зачисляем…`
              : t`Зачислить готовых · ${preview?.counts.ready ?? 0}`}
          </Button>
        </div>
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
        {preview ? (
          <div className="max-h-80 overflow-auto rounded-md border border-border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-16">
                    <Trans>Строка</Trans>
                  </TableHead>
                  <TableHead>
                    <Trans>Школьник и курс</Trans>
                  </TableHead>
                  <TableHead>
                    <Trans>Активная группа</Trans>
                  </TableHead>
                  <TableHead>
                    <Trans>Доступные группы</Trans>
                  </TableHead>
                  <TableHead>
                    <Trans>Результат</Trans>
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {preview.rows.slice(0, 100).map((row) => (
                  <TableRow key={row.rowNumber}>
                    <TableCell>{row.rowNumber}</TableCell>
                    {row.state === 'ready' ? (
                      <>
                        <TableCell className="font-mono text-caption">
                          {row.login} · {row.courseCode}
                        </TableCell>
                        <TableCell>{row.activeGroupCode}</TableCell>
                        <TableCell>{row.allowedGroupCodes.join(', ')}</TableCell>
                        <TableCell>
                          <Trans>Готово</Trans>
                        </TableCell>
                      </>
                    ) : (
                      <TableCell colSpan={4}>{diagnosticLabels[row.code] ?? row.code}</TableCell>
                    )}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        ) : null}
        {receipt ? (
          <Alert tone={receipt.counts.skipped ? 'warning' : 'success'}>
            <AlertContent>
              <AlertTitle>
                <Trans>Зачисление обработано</Trans>
              </AlertTitle>
              <AlertDescription>
                <Trans>
                  Зачислено: {receipt.counts.created}. Пропущено: {receipt.counts.skipped}.
                </Trans>
              </AlertDescription>
            </AlertContent>
          </Alert>
        ) : null}
      </CardContent>
    </Card>
  )
}

export function AccountProvisioningView({
  accountId,
  storageNamespace,
  onSectionChange,
  previewStudents,
  applyStudents,
  previewFamilies,
  applyFamilies,
  previewCourseEnrollments,
  applyCourseEnrollments,
}: {
  accountId: string
  storageNamespace: string
  onSectionChange: (section: UsersSection) => void
  previewStudents: (rows: StudentProvisioningRow[]) => Promise<AccountProvisioningPreviewResponse>
  applyStudents: (
    rows: StudentProvisioningRow[],
    preview: AccountProvisioningPreviewResponse,
    onProgress?: (processed: number, total: number) => void,
    onChunkCompleted?: (rows: AccountProvisioningReceipt['rows']) => void,
  ) => Promise<AccountProvisioningReceipt>
  previewFamilies: (rows: FamilyProvisioningRow[]) => Promise<AccountProvisioningPreviewResponse>
  applyFamilies: (
    rows: FamilyProvisioningRow[],
    preview: AccountProvisioningPreviewResponse,
    onProgress?: (processed: number, total: number) => void,
    onChunkCompleted?: (rows: AccountProvisioningReceipt['rows']) => void,
  ) => Promise<AccountProvisioningReceipt>
  previewCourseEnrollments: (
    rows: CourseEnrollmentProvisioningRow[],
  ) => Promise<CourseEnrollmentProvisioningPreviewResponse>
  applyCourseEnrollments: (
    rows: CourseEnrollmentProvisioningRow[],
    preview: CourseEnrollmentProvisioningPreviewResponse,
  ) => Promise<CourseEnrollmentProvisioningReceipt>
}) {
  return (
    <PageLayout
      description={t`Сначала создайте школьников, затем аккаунты родителей. Зачисление на курс выполняется отдельным действием.`}
      eyebrow="Admin"
      title={t`Пакетное создание аккаунтов`}
      width="wide"
    >
      <div className="space-y-4">
        <UsersSectionTabs onChange={onSectionChange} section="imports" showImports showTeachers />
        <Alert>
          <AlertContent>
            <AlertTitle>
              <Trans>Данные для входа</Trans>
            </AlertTitle>
            <AlertDescription>
              <Trans>
                В первой версии пароли хранятся для внешней почтовой рассылки. Не вставляйте сюда
                production-данные на общем устройстве.
              </Trans>
            </AlertDescription>
          </AlertContent>
        </Alert>
        <ProvisioningPanel
          applyRequest={applyStudents}
          audience="student"
          columns={t`Фамилия · Имя · Отчество · Дата рождения · Класс · Логин · Пароль`}
          description={t`Отчество, дата рождения и класс могут быть пустыми. Дата: ДД.ММ.ГГГГ или ГГГГ-ММ-ДД.`}
          draftKey={provisioningDraftKey(storageNamespace, accountId, 'student')}
          parse={parseStudentProvisioningTsv}
          previewRequest={previewStudents}
          serialize={serializeStudentProvisioningTsv}
        />
        <ProvisioningPanel
          applyRequest={applyFamilies}
          audience="family"
          columns={t`Имя · Логин · Пароль · Email через запятую · Логины детей через запятую`}
          description={t`Родительский пакет запускайте после создания школьников. Один аккаунт может быть связан с несколькими детьми.`}
          draftKey={provisioningDraftKey(storageNamespace, accountId, 'family')}
          parse={parseFamilyProvisioningTsv}
          previewRequest={previewFamilies}
          serialize={serializeFamilyProvisioningTsv}
        />
        <CourseEnrollmentProvisioningPanel
          applyRequest={applyCourseEnrollments}
          draftKey={provisioningDraftKey(storageNamespace, accountId, 'course-enrollment')}
          previewRequest={previewCourseEnrollments}
        />
      </div>
    </PageLayout>
  )
}

export function StaffAccountProvisioningPage({
  onSectionChange,
}: {
  onSectionChange: (section: UsersSection) => void
}) {
  const authentication = useAuthentication()
  const principal = useAuthenticatedPrincipal()
  if (principal.audience !== 'staff') throw new Error('Provisioning requires Staff auth')
  const client = useMemo(
    () =>
      createAdminCourseClient(authentication.client.runtime, {
        refreshSession: () => authentication.refresh(),
      }),
    [authentication],
  )
  if (principal.role !== 'admin') {
    return (
      <PageLayout title={t`Пакетное создание аккаунтов`}>
        <PageStatePanel state="forbidden" />
      </PageLayout>
    )
  }
  const handle = async <T,>(operation: () => Promise<T>) => {
    try {
      return await operation()
    } catch (error) {
      authentication.handleApiError(error)
      throw error
    }
  }
  return (
    <AccountProvisioningView
      accountId={principal.accountId}
      applyCourseEnrollments={(rows, preview) =>
        handle(() =>
          client.applyCourseEnrollments({
            schemaVersion: 1,
            rows,
            previewHash: preview.previewHash,
          }),
        )
      }
      applyFamilies={(rows, preview, onProgress, onChunkCompleted) =>
        handle(() =>
          applyProvisioningInChunks({
            rows,
            initialPreview: preview,
            preview: (chunk) => client.previewFamilyAccounts({ schemaVersion: 1, rows: chunk }),
            apply: (chunk, current) =>
              client.applyFamilyAccounts({
                schemaVersion: 1,
                rows: chunk,
                resolvedLogins: current.rows.map((row) => row.resolvedLogin),
                previewHash: current.previewHash,
              }),
            onProgress,
            onChunkCompleted,
          }),
        )
      }
      applyStudents={(rows, preview, onProgress, onChunkCompleted) =>
        handle(() =>
          applyProvisioningInChunks({
            rows,
            initialPreview: preview,
            preview: (chunk) => client.previewStudentAccounts({ schemaVersion: 1, rows: chunk }),
            apply: (chunk, current) =>
              client.applyStudentAccounts({
                schemaVersion: 1,
                rows: chunk,
                resolvedLogins: current.rows.map((row) => row.resolvedLogin),
                previewHash: current.previewHash,
              }),
            onProgress,
            onChunkCompleted,
          }),
        )
      }
      onSectionChange={onSectionChange}
      previewFamilies={(rows) =>
        handle(() => client.previewFamilyAccounts({ schemaVersion: 1, rows }))
      }
      previewCourseEnrollments={(rows) =>
        handle(() => client.previewCourseEnrollments({ schemaVersion: 1, rows }))
      }
      previewStudents={(rows) =>
        handle(() => client.previewStudentAccounts({ schemaVersion: 1, rows }))
      }
      storageNamespace={createBrowserStorageNamespace(authentication.client.runtime)}
    />
  )
}
