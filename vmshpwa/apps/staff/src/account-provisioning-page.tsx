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
  parseFamilyProvisioningTsv,
  parseStudentProvisioningTsv,
  provisioningDraftKey,
} from './account-provisioning-tsv'
import { UsersSectionTabs, type UsersSection } from './users-section-tabs'

const diagnosticLabels: Record<string, string> = {
  invalid_student_row: 'неверное число или название столбцов',
  invalid_family_row: 'неверное число или название столбцов',
  invalid_surname: 'проверьте фамилию',
  invalid_name: 'проверьте имя',
  invalid_patronymic: 'проверьте отчество',
  invalid_birth_date: 'проверьте дату рождения',
  invalid_grade: 'класс должен быть от 1 до 11',
  invalid_login: 'проверьте логин',
  invalid_password: 'проверьте пароль',
  invalid_emails: 'проверьте список email',
  invalid_child_logins: 'проверьте логины детей',
  child_login_not_found: 'школьник с таким логином не найден',
  student_token_conflict: 'такой Telegram-токен уже используется',
  login_suffix_exhausted: 'не удалось подобрать свободный логин',
  account_conflict: 'данные изменились после предпросмотра',
  invalid_row: 'строка не прошла проверку',
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
  return 'Не удалось выполнить действие. Проверьте соединение и повторите попытку.'
}

function ProvisioningPanel<Row extends StudentProvisioningRow | FamilyProvisioningRow>({
  audience,
  columns,
  description,
  draftKey,
  parse,
  previewRequest,
  applyRequest,
}: {
  audience: 'student' | 'family'
  columns: string
  description: string
  draftKey: string
  parse: (source: string) => Row[]
  previewRequest: (rows: Row[]) => Promise<AccountProvisioningPreviewResponse>
  applyRequest: (
    rows: Row[],
    preview: AccountProvisioningPreviewResponse,
  ) => Promise<AccountProvisioningReceipt>
}) {
  const [source, setSource] = useState(() => readDraft(draftKey))
  const [rows, setRows] = useState<Row[] | null>(null)
  const [preview, setPreview] = useState<AccountProvisioningPreviewResponse | null>(null)
  const [receipt, setReceipt] = useState<AccountProvisioningReceipt | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState<'preview' | 'apply' | null>(null)
  const [storageAvailable, setStorageAvailable] = useState(true)
  const title = audience === 'student' ? '1. Школьники' : '2. Родители'

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
      const parsed = parse(source)
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
          <CardTitle>{title}</CardTitle>
          {preview ? (
            <div className="flex gap-1">
              <Badge variant="success">Готовы: {preview.counts.ready}</Badge>
              {preview.counts.invalid ? (
                <Badge variant="warning">Проверить: {preview.counts.invalid}</Badge>
              ) : null}
            </div>
          ) : null}
        </div>
        <p className="text-small text-muted-foreground">{description}</p>
      </CardHeader>
      <CardContent className="space-y-3">
        <Label className="grid gap-1 text-small">
          Вставьте строки из таблицы
          <Textarea
            className="min-h-36 font-mono text-caption"
            onChange={(event) => changeSource(event.target.value)}
            placeholder={columns}
            spellCheck={false}
            value={source}
          />
        </Label>
        <p className="text-caption text-muted-foreground">
          Порядок столбцов: {columns}. Пустые необязательные ячейки оставляйте пустыми; разделители
          между столбцами должны оставаться табуляцией.
        </p>
        {!storageAvailable ? (
          <p className="text-small text-status-error" role="alert">
            Черновик не сохраняется в этом браузере. Не закрывайте вкладку.
          </p>
        ) : (
          <p className="text-caption text-muted-foreground" role="status">
            Вставленный текст сохраняется только в этом браузере до успешного создания аккаунтов.
          </p>
        )}

        <div className="flex flex-wrap gap-2">
          <Button
            disabled={!source.trim() || pending !== null}
            onClick={() => void previewRows()}
            type="button"
          >
            {pending === 'preview' ? 'Проверяем…' : 'Проверить таблицу'}
          </Button>
          <Button
            disabled={!preview?.counts.ready || pending !== null}
            onClick={() => void applyRows()}
            type="button"
            variant="outline"
          >
            {pending === 'apply' ? 'Создаём…' : `Создать готовые · ${preview?.counts.ready ?? 0}`}
          </Button>
        </div>

        {error ? (
          <Alert role="alert" tone="danger">
            <AlertContent>
              <AlertTitle>Не удалось продолжить</AlertTitle>
              <AlertDescription>{error}</AlertDescription>
            </AlertContent>
          </Alert>
        ) : null}

        {preview ? (
          <div className="max-h-80 overflow-auto rounded-md border border-border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-16">Строка</TableHead>
                  <TableHead>Итоговый логин</TableHead>
                  <TableHead>Результат</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {preview.rows.slice(0, 100).map((row) => (
                  <TableRow key={row.rowNumber}>
                    <TableCell>{row.rowNumber}</TableCell>
                    <TableCell className="font-mono text-caption">
                      {row.resolvedLogin ?? '—'}
                      {row.state === 'ready' && row.loginAdjusted ? ' · изменён' : ''}
                    </TableCell>
                    <TableCell>
                      {row.state === 'ready' ? 'Готово' : (diagnosticLabels[row.code] ?? row.code)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        ) : null}
        {preview && preview.rows.length > 100 ? (
          <p className="text-caption text-muted-foreground">
            Показаны первые 100 из {preview.rows.length}; итоговые счётчики учитывают все строки.
          </p>
        ) : null}
        {receipt ? (
          <Alert tone={receipt.counts.skipped ? 'warning' : 'success'}>
            <AlertContent>
              <AlertTitle>Пакет обработан</AlertTitle>
              <AlertDescription>
                Создано: {receipt.counts.created}. Пропущено: {receipt.counts.skipped}.
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
}: {
  accountId: string
  storageNamespace: string
  onSectionChange: (section: UsersSection) => void
  previewStudents: (rows: StudentProvisioningRow[]) => Promise<AccountProvisioningPreviewResponse>
  applyStudents: (
    rows: StudentProvisioningRow[],
    preview: AccountProvisioningPreviewResponse,
  ) => Promise<AccountProvisioningReceipt>
  previewFamilies: (rows: FamilyProvisioningRow[]) => Promise<AccountProvisioningPreviewResponse>
  applyFamilies: (
    rows: FamilyProvisioningRow[],
    preview: AccountProvisioningPreviewResponse,
  ) => Promise<AccountProvisioningReceipt>
}) {
  return (
    <PageLayout
      description="Сначала создайте школьников, затем семейные аккаунты. Зачисление на курс выполняется отдельным действием."
      eyebrow="Admin"
      title="Пакетное создание аккаунтов"
      width="wide"
    >
      <div className="space-y-4">
        <UsersSectionTabs onChange={onSectionChange} section="imports" showImports showTeachers />
        <Alert>
          <AlertContent>
            <AlertTitle>Данные для входа</AlertTitle>
            <AlertDescription>
              В первой версии пароли хранятся для внешней почтовой рассылки. Не вставляйте сюда
              production-данные на общем устройстве.
            </AlertDescription>
          </AlertContent>
        </Alert>
        <ProvisioningPanel
          applyRequest={applyStudents}
          audience="student"
          columns="Фамилия · Имя · Отчество · Дата рождения · Класс · Логин · Пароль"
          description="Отчество, дата рождения и класс могут быть пустыми. Дата: ДД.ММ.ГГГГ или ГГГГ-ММ-ДД."
          draftKey={provisioningDraftKey(storageNamespace, accountId, 'student')}
          parse={parseStudentProvisioningTsv}
          previewRequest={previewStudents}
        />
        <ProvisioningPanel
          applyRequest={applyFamilies}
          audience="family"
          columns="Имя · Логин · Пароль · Email через запятую · Логины детей через запятую"
          description="Семейный пакет запускайте после создания школьников. Один аккаунт может быть связан с несколькими детьми."
          draftKey={provisioningDraftKey(storageNamespace, accountId, 'family')}
          parse={parseFamilyProvisioningTsv}
          previewRequest={previewFamilies}
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
      <PageLayout title="Пакетное создание аккаунтов">
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
      applyFamilies={(rows, preview) =>
        handle(() =>
          client.applyFamilyAccounts({
            schemaVersion: 1,
            rows,
            resolvedLogins: preview.rows.map((row) => row.resolvedLogin),
            previewHash: preview.previewHash,
          }),
        )
      }
      applyStudents={(rows, preview) =>
        handle(() =>
          client.applyStudentAccounts({
            schemaVersion: 1,
            rows,
            resolvedLogins: preview.rows.map((row) => row.resolvedLogin),
            previewHash: preview.previewHash,
          }),
        )
      }
      onSectionChange={onSectionChange}
      previewFamilies={(rows) =>
        handle(() => client.previewFamilyAccounts({ schemaVersion: 1, rows }))
      }
      previewStudents={(rows) =>
        handle(() => client.previewStudentAccounts({ schemaVersion: 1, rows }))
      }
      storageNamespace={createBrowserStorageNamespace(authentication.client.runtime)}
    />
  )
}
