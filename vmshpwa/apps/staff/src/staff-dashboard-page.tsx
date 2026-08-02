import { BookOpenCheck, CircleAlert, ClipboardCheck, MessagesSquare, Radio } from 'lucide-react'
import { useMemo } from 'react'

import {
  PageLayout,
  PageSection,
  PageStatePanel,
  createStaffDashboardClient,
  useAuthenticatedPrincipal,
  useAuthentication,
  useStaffDashboardQuery,
} from '@vmsh/app-shell'
import { ApiResponseError, type StaffDashboardResponse } from '@vmsh/contracts'
import { Badge, Card, CardContent, CardHeader, CardTitle } from '@vmsh/ui'

/*
 * Operational scope and card contents are fixed by development-plan/14-phase-10-admin-and-google-exit.md.
 * The API returns aggregates and one current lesson per visible group; Student rows stay inside the
 * dedicated review and support screens. Contract proof: packages/contracts/src/staff-dashboard.test.ts.
 */

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

function SummaryCard({
  href,
  icon: Icon,
  label,
  value,
  detail,
  warning = false,
}: {
  href: string
  icon: typeof ClipboardCheck
  label: string
  value: number
  detail: string
  warning?: boolean
}) {
  return (
    <a
      className="block rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      href={href}
    >
      <Card className="h-full transition-colors hover:border-strong" size="sm">
        <CardHeader className="grid grid-cols-[1fr_auto] items-center">
          <CardTitle className="text-caption font-medium text-muted-foreground">{label}</CardTitle>
          <Icon
            aria-hidden="true"
            className={warning ? 'size-4 text-destructive' : 'size-4 text-muted-foreground'}
          />
        </CardHeader>
        <CardContent>
          <div className="font-num text-title font-semibold">{value}</div>
          <p className="mt-1 text-caption text-muted-foreground">{detail}</p>
        </CardContent>
      </Card>
    </a>
  )
}

function PublicationBadge({ state }: { state: 'none' | 'scheduled' | 'published' }) {
  return (
    <Badge variant={state === 'published' ? 'success' : state === 'scheduled' ? 'info' : 'neutral'}>
      {publicationLabels[state]}
    </Badge>
  )
}

export function StaffDashboardView({ data }: { data: StaffDashboardResponse }) {
  const { summary } = data
  return (
    <PageLayout
      description="Текущие занятия, публикации и входящая работа в доступных вам курсах и группах."
      title="Рабочая сводка"
      width="wide"
    >
      <div className="space-y-6">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-5">
          <SummaryCard
            detail={
              summary.review.claimedByOthers === 0
                ? 'Все доступны вам'
                : `${summary.review.claimedByOthers} у коллег`
            }
            href="/staff/review"
            icon={ClipboardCheck}
            label="Ожидают проверки"
            value={summary.review.totalCases}
          />
          <SummaryCard
            detail={
              summary.questions.olderThanOneHour === 0
                ? 'Старых вопросов нет'
                : `${summary.questions.olderThanOneHour} ждут больше часа`
            }
            href="/staff/questions"
            icon={MessagesSquare}
            label="Вопросы"
            value={summary.questions.awaitingStaff}
            warning={summary.questions.olderThanOneHour > 0}
          />
          <SummaryCard
            detail={`${summary.publications.conditionsPublished} условий опубликовано`}
            href="/staff/lessons"
            icon={BookOpenCheck}
            label="Текущие листки"
            value={summary.publications.groupLessons}
          />
          <SummaryCard
            detail={`${summary.oral.upcomingWindows} откроются позже`}
            href="/staff/oral"
            icon={Radio}
            label="Устные окна открыты"
            value={summary.oral.openWindows}
          />
          {summary.delivery ? (
            <SummaryCard
              detail={`${summary.delivery.failedBatches} рассылок требуют внимания`}
              href="/staff/classrooms"
              icon={CircleAlert}
              label="Не доставлены аудитории"
              value={summary.delivery.failedRecipients}
              warning={summary.delivery.failedRecipients > 0}
            />
          ) : null}
        </div>

        <PageSection
          description="Для каждой доступной группы показано последнее начавшееся занятие или ближайшее предстоящее."
          title="Занятия по группам"
        >
          {data.lessons.length === 0 ? (
            <PageStatePanel
              description="Создайте занятие или попросите администратора выдать доступ к группе."
              state="empty"
              title="Текущих занятий нет"
            />
          ) : (
            <div className="grid gap-3 lg:grid-cols-2 xl:grid-cols-3">
              {data.lessons.map((lesson) => (
                <Card key={lesson.groupLessonId}>
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
                  <CardContent className="space-y-3">
                    <dl className="grid grid-cols-[auto_1fr] items-center gap-x-3 gap-y-2 text-small">
                      <dt className="text-muted-foreground">Условие</dt>
                      <dd>
                        <PublicationBadge state={lesson.publications.condition.state} />
                      </dd>
                      <dt className="text-muted-foreground">Подсказка</dt>
                      <dd>
                        <PublicationBadge state={lesson.publications.hint.state} />
                      </dd>
                      <dt className="text-muted-foreground">Решение</dt>
                      <dd>
                        <PublicationBadge state={lesson.publications.solution.state} />
                      </dd>
                    </dl>
                    {lesson.oral.openWindows + lesson.oral.upcomingWindows > 0 ? (
                      <p className="border-t border-border pt-3 text-caption text-muted-foreground">
                        Устно: открыто {lesson.oral.openWindows}, позже{' '}
                        {lesson.oral.upcomingWindows}
                      </p>
                    ) : null}
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </PageSection>
      </div>
    </PageLayout>
  )
}

export function StaffDashboardPage() {
  const authentication = useAuthentication()
  const principal = useAuthenticatedPrincipal()
  if (principal.audience !== 'staff') throw new Error('Dashboard requires Staff auth')
  const client = useMemo(
    () =>
      createStaffDashboardClient(authentication.client.runtime, {
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
  const result = useStaffDashboardQuery(client, {
    audience: 'staff',
    accountId: principal.accountId,
  })

  if (result.isPending) {
    return (
      <PageLayout title="Рабочая сводка" width="wide">
        <PageStatePanel state="loading" />
      </PageLayout>
    )
  }
  if (result.error) {
    return (
      <PageLayout title="Рабочая сводка" width="wide">
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
  return <StaffDashboardView data={result.data} />
}
