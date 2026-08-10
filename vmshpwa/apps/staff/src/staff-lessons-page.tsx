import { BookOpenCheck, FileUp } from 'lucide-react'
import { useMemo } from 'react'

import {
  PageLayout,
  PageStatePanel,
  createStaffDashboardClient,
  useAuthenticatedPrincipal,
  useAuthentication,
  useStaffDashboardQuery,
} from '@vmsh/app-shell'
import { ApiResponseError } from '@vmsh/contracts'
import { Badge, Button, Card, CardContent, CardHeader, CardTitle } from '@vmsh/ui'

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
        <Button disabled title="Сначала создайте занятие">
          <FileUp /> Загрузить LaTeX
        </Button>
      }
      description="Здесь отображаются только занятия и публикации, сохранённые в базе данных."
      eyebrow="LaTeX — единственный источник"
      title="Уроки и публикации"
      width="wide"
    >
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
