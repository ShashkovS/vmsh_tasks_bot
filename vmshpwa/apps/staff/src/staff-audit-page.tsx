import { t } from '@lingui/core/macro'
import { Trans } from '@lingui/react/macro'
import { currentLocale, dateTimeFormat } from '@vmsh/i18n'
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
  get all() {
    return t`Все объекты`
  },
  get account() {
    return t`Аккаунты`
  },
  get family_link() {
    return t`Связи с родителями`
  },
  get course_enrollment() {
    return t`Участники курсов`
  },
  get problem_import() {
    return t`Импорт задач`
  },
  get course() {
    return t`Курсы`
  },
  get group() {
    return t`Группы`
  },
  get telegram_binding() {
    return t`Привязки Telegram`
  },
  get problem_synonym() {
    return t`Синонимы задач`
  },
  get news_post() {
    return t`Публикации`
  },
  get staff_scope() {
    return t`Доступы преподавателей`
  },
}

const actionLabels: Record<string, string> = {
  get 'student.account_created'() {
    return t`Создан вход школьника`
  },
  get 'family.account_created'() {
    return t`Создан вход родителя`
  },
  get 'family.student_linked'() {
    return t`Добавлена связь с родителем`
  },
  get 'family.student_unlinked'() {
    return t`Удалена связь с родителем`
  },
  get 'account.status_changed'() {
    return t`Изменён статус аккаунта`
  },
  get 'account.credential_changed'() {
    return t`Заменены данные для входа`
  },
  get 'course_enrollment.updated'() {
    return t`Изменено участие в курсе`
  },
  get 'problem_import.applied'() {
    return t`Применён импорт задач`
  },
  get 'problem_import.rolled_back'() {
    return t`Отменён импорт задач`
  },
  get 'course.created'() {
    return t`Создан курс`
  },
  get 'course.updated'() {
    return t`Изменён курс`
  },
  get 'group.created'() {
    return t`Создана группа`
  },
  get 'group.updated'() {
    return t`Изменена группа`
  },
  get 'telegram_binding.created'() {
    return t`Создана привязка Telegram`
  },
  get 'telegram_binding.updated'() {
    return t`Изменена привязка Telegram`
  },
  get 'telegram_binding.disabled'() {
    return t`Отключена привязка Telegram`
  },
  get 'telegram_binding.draft_restored'() {
    return t`Привязка возвращена в черновик`
  },
  get 'telegram_binding.verified'() {
    return t`Проверена привязка Telegram`
  },
  get 'problem_synonym.merged'() {
    return t`Задачи объединены в синонимы`
  },
  get 'problem_synonym.split'() {
    return t`Задачи разделены`
  },
  get 'news_source.marked_deleted'() {
    return t`Пост отмечен удалённым в Telegram`
  },
  get 'news_source.marked_present'() {
    return t`Пост отмечен доступным в Telegram`
  },
  get 'news_local.created'() {
    return t`Создана публикация в PWA`
  },
  get 'staff_scope.replaced'() {
    return t`Изменены доступы преподавателя`
  },
}

const fieldLabels: Record<string, string> = {
  get activeGroupId() {
    return t`Активная группа`
  },
  get accentKey() {
    return t`Цвет курса`
  },
  get allowedGroupIds() {
    return t`Доступные группы`
  },
  get addedCount() {
    return t`Добавлено задач`
  },
  get attendanceMode() {
    return t`Режим участия`
  },
  get audience() {
    return t`Кабинет`
  },
  get courseId() {
    return t`Курс`
  },
  get courseLessonId() {
    return t`Занятие курса`
  },
  get chatId() {
    return t`Чат`
  },
  get code() {
    return t`Код`
  },
  get colorKey() {
    return t`Цвет группы`
  },
  get created() {
    return t`Создано задач`
  },
  get credentialVersion() {
    return t`Версия данных для входа`
  },
  get isPrimary() {
    return t`Основная связь`
  },
  get allowSelfSwitch() {
    return t`Самостоятельная смена`
  },
  get linked() {
    return t`Связь активна`
  },
  get messageThreadId() {
    return t`Тема чата`
  },
  get memberCount() {
    return t`Задач в группе`
  },
  get ownerId() {
    return t`Владелец`
  },
  get ownerType() {
    return t`Тип владельца`
  },
  get purpose() {
    return t`Назначение`
  },
  get publishedAt() {
    return t`Время публикации`
  },
  get reason() {
    return t`Причина`
  },
  get reconciliationReason() {
    return t`Причина сверки`
  },
  get removedCount() {
    return t`Удалено задач`
  },
  get relationshipLabel() {
    return t`Роль родителя`
  },
  get rows() {
    return t`Строк обработано`
  },
  get scoreWeight() {
    return t`Вес результатов`
  },
  get scopeCount() {
    return t`Областей доступа`
  },
  get scopes() {
    return t`Курсы и группы`
  },
  get shortCode() {
    return t`Короткий код`
  },
  get sortOrder() {
    return t`Порядок`
  },
  get sourceFilename() {
    return t`Исходный файл`
  },
  get sourceDeletedAt() {
    return t`Удалено в источнике`
  },
  get state() {
    return t`Состояние`
  },
  get status() {
    return t`Статус`
  },
  get studentId() {
    return t`Школьник`
  },
  get subjectCode() {
    return t`Предмет`
  },
  get titleCached() {
    return t`Название в Telegram`
  },
  get updated() {
    return t`Изменено задач`
  },
  get username() {
    return t`Логин`
  },
  get version() {
    return t`Версия`
  },
  get verifiedAt() {
    return t`Проверено`
  },
  get visibility() {
    return t`Видимость`
  },
}

function dateTime(value: string): string {
  return dateTimeFormat(currentLocale(), {
    dateStyle: 'short',
    timeStyle: 'medium',
    timeZone: 'Europe/Moscow',
  }).format(new Date(value))
}

function displayValue(value: string | number | boolean | null | undefined): string {
  if (value === undefined || value === null) return '—'
  if (value === true) return t`да`
  if (value === false) return t`нет`
  return String(value)
}

function AuditChanges({ event }: { event: AuditEvent }) {
  const keys = Array.from(
    new Set([...Object.keys(event.before ?? {}), ...Object.keys(event.after ?? {})]),
  ).sort((left, right) => left.localeCompare(right, 'ru'))
  if (keys.length === 0)
    return (
      <span className="text-muted-foreground">
        <Trans>без полей</Trans>
      </span>
    )
  return (
    <details className="min-w-64">
      <summary className="cursor-pointer text-small font-medium text-link">
        <Trans>Показать изменения</Trans>
      </summary>
      <dl className="mt-2 grid grid-cols-[minmax(8rem,1fr)_minmax(7rem,1fr)_minmax(7rem,1fr)] gap-x-3 gap-y-1 rounded-md border border-border bg-surface-subtle p-2 text-caption">
        <dt className="font-medium text-muted-foreground">
          <Trans>Поле</Trans>
        </dt>
        <dd className="font-medium text-muted-foreground">
          <Trans>Было</Trans>
        </dd>
        <dd className="font-medium text-muted-foreground">
          <Trans>Стало</Trans>
        </dd>
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
      description={t`Административные изменения с исполнителем, request ID и безопасным сравнением значений. Пароли и токены сюда не записываются.`}
      title={t`Журнал изменений`}
      width="wide"
    >
      <form
        className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-end"
        key={`${objectType}:${query}`}
        onSubmit={submit}
      >
        <Label className="grid min-w-52 gap-1 text-caption">
          <Trans>Объект</Trans>
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
          <Trans>Поиск по действию, объекту или request ID</Trans>
          <Input
            defaultValue={query}
            maxLength={100}
            name="q"
            placeholder={t`Например, request-2026-08-02`}
          />
        </Label>
        <Button type="submit" variant="outline">
          <Search aria-hidden="true" />
          <Trans>Найти</Trans>
        </Button>
      </form>

      {events.length === 0 ? (
        <PageStatePanel
          description={t`Попробуйте изменить фильтр или строку поиска.`}
          state="empty"
          title={t`Изменений не найдено`}
        />
      ) : (
        <div className="overflow-hidden rounded-lg border border-border bg-surface">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>
                  <Trans>Когда</Trans>
                </TableHead>
                <TableHead>
                  <Trans>Действие</Trans>
                </TableHead>
                <TableHead>
                  <Trans>Объект</Trans>
                </TableHead>
                <TableHead>
                  <Trans>Кто</Trans>
                </TableHead>
                <TableHead>Request ID</TableHead>
                <TableHead>
                  <Trans>Изменения</Trans>
                </TableHead>
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
            <Trans>Следующая страница</Trans>
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
      <PageLayout title={t`Журнал изменений`} width="wide">
        <PageStatePanel state="loading" />
      </PageLayout>
    )
  }
  if (result.error) {
    return (
      <PageLayout title={t`Журнал изменений`} width="wide">
        <PageStatePanel
          actionLabel={t`Повторить`}
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
