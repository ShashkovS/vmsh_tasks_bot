import { ChevronRight, Search } from 'lucide-react'
import { useMemo, type FormEvent } from 'react'

import {
  PageLayout,
  PageStatePanel,
  createAuditClient,
  useAuditQuery,
  useAuthenticatedPrincipal,
  useAuthentication,
} from '@vmsh/app-shell'
import { ApiResponseError, type AuditEvent, type AuditObjectType } from '@vmsh/contracts'
import {
  Badge,
  Button,
  Input,
  Label,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@vmsh/ui'

const objectLabels: Record<AuditObjectType, string> = {
  all: 'Все объекты',
  account: 'Аккаунты',
  family_link: 'Связи с семьёй',
  course_enrollment: 'Участники курсов',
  problem_import: 'Импорт задач',
  course: 'Курсы',
  group: 'Группы',
  telegram_binding: 'Привязки Telegram',
  problem_synonym: 'Синонимы задач',
  staff_scope: 'Доступы преподавателей',
}

const actionLabels: Record<string, string> = {
  'student.account_created': 'Создан вход школьника',
  'family.account_created': 'Создан семейный вход',
  'family.student_linked': 'Добавлена связь с семьёй',
  'family.student_unlinked': 'Удалена связь с семьёй',
  'account.status_changed': 'Изменён статус аккаунта',
  'account.credential_changed': 'Заменены данные для входа',
  'course_enrollment.updated': 'Изменено участие в курсе',
  'problem_import.applied': 'Применён импорт задач',
  'problem_import.rolled_back': 'Отменён импорт задач',
  'course.created': 'Создан курс',
  'course.updated': 'Изменён курс',
  'group.created': 'Создана группа',
  'group.updated': 'Изменена группа',
  'telegram_binding.created': 'Создана привязка Telegram',
  'telegram_binding.updated': 'Изменена привязка Telegram',
  'telegram_binding.disabled': 'Отключена привязка Telegram',
  'telegram_binding.draft_restored': 'Привязка возвращена в черновик',
  'telegram_binding.verified': 'Проверена привязка Telegram',
  'problem_synonym.merged': 'Задачи объединены в синонимы',
  'problem_synonym.split': 'Задачи разделены',
  'staff_scope.replaced': 'Изменены доступы преподавателя',
}

const fieldLabels: Record<string, string> = {
  activeGroupId: 'Активная группа',
  accentKey: 'Цвет курса',
  allowedGroupIds: 'Доступные группы',
  addedCount: 'Добавлено задач',
  attendanceMode: 'Режим участия',
  audience: 'Кабинет',
  courseId: 'Курс',
  courseLessonId: 'Занятие курса',
  chatId: 'Чат',
  code: 'Код',
  colorKey: 'Цвет группы',
  created: 'Создано задач',
  credentialVersion: 'Версия данных для входа',
  isPrimary: 'Основная связь',
  allowSelfSwitch: 'Самостоятельная смена',
  linked: 'Связь активна',
  messageThreadId: 'Тема чата',
  memberCount: 'Задач в группе',
  ownerId: 'Владелец',
  ownerType: 'Тип владельца',
  purpose: 'Назначение',
  reason: 'Причина',
  removedCount: 'Удалено задач',
  relationshipLabel: 'Роль в семье',
  rows: 'Строк обработано',
  scoreWeight: 'Вес результатов',
  scopeCount: 'Областей доступа',
  scopes: 'Курсы и группы',
  shortCode: 'Короткий код',
  sortOrder: 'Порядок',
  sourceFilename: 'Исходный файл',
  state: 'Состояние',
  status: 'Статус',
  studentId: 'Школьник',
  subjectCode: 'Предмет',
  titleCached: 'Название в Telegram',
  updated: 'Изменено задач',
  username: 'Логин',
  version: 'Версия',
  verifiedAt: 'Проверено',
}

function dateTime(value: string): string {
  return new Intl.DateTimeFormat('ru-RU', {
    dateStyle: 'short',
    timeStyle: 'medium',
    timeZone: 'Europe/Moscow',
  }).format(new Date(value))
}

function displayValue(value: string | number | boolean | null | undefined): string {
  if (value === undefined || value === null) return '—'
  if (value === true) return 'да'
  if (value === false) return 'нет'
  return String(value)
}

function AuditChanges({ event }: { event: AuditEvent }) {
  const keys = Array.from(
    new Set([...Object.keys(event.before ?? {}), ...Object.keys(event.after ?? {})]),
  ).sort((left, right) => left.localeCompare(right, 'ru'))
  if (keys.length === 0) return <span className="text-muted-foreground">без полей</span>
  return (
    <details className="min-w-64">
      <summary className="cursor-pointer text-small font-medium text-link">
        Показать изменения
      </summary>
      <dl className="mt-2 grid grid-cols-[minmax(8rem,1fr)_minmax(7rem,1fr)_minmax(7rem,1fr)] gap-x-3 gap-y-1 rounded-md border border-border bg-surface-subtle p-2 text-caption">
        <dt className="font-medium text-muted-foreground">Поле</dt>
        <dd className="font-medium text-muted-foreground">Было</dd>
        <dd className="font-medium text-muted-foreground">Стало</dd>
        {keys.map((key) => (
          <div className="col-span-3 grid grid-cols-subgrid border-t border-border pt-1" key={key}>
            <dt>{fieldLabels[key] ?? key}</dt>
            <dd className="break-words">{displayValue(event.before?.[key])}</dd>
            <dd className="break-words">{displayValue(event.after?.[key])}</dd>
          </div>
        ))}
      </dl>
    </details>
  )
}

export function StaffAuditView({
  events,
  nextCursor,
  objectType,
  query,
  onFilter,
  onNextPage,
}: {
  events: AuditEvent[]
  nextCursor: string | null
  objectType: AuditObjectType
  query: string
  onFilter: (objectType: AuditObjectType, query: string) => void
  onNextPage: (cursor: string) => void
}) {
  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const values = new FormData(event.currentTarget)
    const nextObjectType = values.get('objectType')
    const nextQuery = values.get('q')
    if (typeof nextObjectType !== 'string' || typeof nextQuery !== 'string') return
    onFilter(nextObjectType as AuditObjectType, nextQuery.trim())
  }

  return (
    <PageLayout
      description="Административные изменения с исполнителем, request ID и безопасным сравнением значений. Пароли и токены сюда не записываются."
      title="Журнал изменений"
      width="wide"
    >
      <form
        className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-end"
        key={`${objectType}:${query}`}
        onSubmit={submit}
      >
        <Label className="grid min-w-52 gap-1 text-caption">
          Объект
          <select
            className="min-h-9 rounded-md border border-input bg-surface px-3 text-small"
            defaultValue={objectType}
            name="objectType"
          >
            {Object.entries(objectLabels).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </Label>
        <Label className="grid min-w-64 flex-1 gap-1 text-caption">
          Поиск по действию, объекту или request ID
          <Input
            defaultValue={query}
            maxLength={100}
            name="q"
            placeholder="Например, request-2026-08-02"
          />
        </Label>
        <Button type="submit" variant="outline">
          <Search aria-hidden="true" />
          Найти
        </Button>
      </form>

      {events.length === 0 ? (
        <PageStatePanel
          description="Попробуйте изменить фильтр или строку поиска."
          state="empty"
          title="Изменений не найдено"
        />
      ) : (
        <div className="overflow-hidden rounded-lg border border-border bg-surface">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Когда</TableHead>
                <TableHead>Действие</TableHead>
                <TableHead>Объект</TableHead>
                <TableHead>Кто</TableHead>
                <TableHead>Request ID</TableHead>
                <TableHead>Изменения</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {events.map((event) => (
                <TableRow key={event.eventId}>
                  <TableCell className="font-mono text-caption">
                    {dateTime(event.occurredAt)}
                  </TableCell>
                  <TableCell className="max-w-64 whitespace-normal">
                    {actionLabels[event.action] ?? event.action}
                  </TableCell>
                  <TableCell>
                    <div className="space-y-0.5">
                      <Badge variant="neutral">{objectLabels[event.objectType]}</Badge>
                      <div className="font-mono text-caption text-muted-foreground">
                        {event.objectId}
                      </div>
                    </div>
                  </TableCell>
                  <TableCell>{event.actor.displayName}</TableCell>
                  <TableCell className="font-mono text-caption">{event.requestId}</TableCell>
                  <TableCell className="whitespace-normal">
                    <AuditChanges event={event} />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
      {nextCursor ? (
        <div className="mt-4 flex justify-end">
          <Button onClick={() => onNextPage(nextCursor)} variant="outline">
            Следующая страница
            <ChevronRight aria-hidden="true" />
          </Button>
        </div>
      ) : null}
    </PageLayout>
  )
}

export function StaffAuditPage({
  objectType,
  query,
  cursor,
  onFilter,
  onNextPage,
}: {
  objectType: AuditObjectType
  query: string
  cursor: string | null
  onFilter: (objectType: AuditObjectType, query: string) => void
  onNextPage: (cursor: string) => void
}) {
  const authentication = useAuthentication()
  const principal = useAuthenticatedPrincipal()
  if (principal.audience !== 'staff') throw new Error('Audit requires Staff auth')
  const client = useMemo(
    () =>
      createAuditClient(authentication.client.runtime, {
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
  const result = useAuditQuery(
    client,
    { audience: 'staff', accountId: principal.accountId },
    { objectType, query, cursor },
  )

  if (result.isPending) {
    return (
      <PageLayout title="Журнал изменений" width="wide">
        <PageStatePanel state="loading" />
      </PageLayout>
    )
  }
  if (result.error) {
    return (
      <PageLayout title="Журнал изменений" width="wide">
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
    <StaffAuditView
      events={result.data.items}
      nextCursor={result.data.nextCursor}
      objectType={objectType}
      onFilter={onFilter}
      onNextPage={onNextPage}
      query={query}
    />
  )
}
