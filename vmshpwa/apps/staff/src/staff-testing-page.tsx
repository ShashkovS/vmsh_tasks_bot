import { t } from '@lingui/core/macro'
import { Trans } from '@lingui/react/macro'
import { pwaFetch } from '@vmsh/contracts'
import { useMutation, useQuery } from '@tanstack/react-query'
import { z } from 'zod'
import { PageLayout, useAuthenticatedPrincipal, useAuthentication } from '@vmsh/app-shell'
import { ApiResponseError, apiErrorSchema, staffTestingCoursesSchema } from '@vmsh/contracts'
import { Button, Card, CardContent, CardHeader, CardTitle } from '@vmsh/ui'

// Student reuse and audience boundaries: docs/staff-testing.md; pages-and-flows § Staff.
export function StaffTestingPage({ view = 'tasks' }: { view?: 'tasks' | 'news' | 'courses' }) {
  const authentication = useAuthentication()
  const principal = useAuthenticatedPrincipal()
  async function request(path: string, method = 'GET') {
    const send = () =>
      pwaFetch(`${authentication.client.runtime.apiBase}/testing/${path}`, {
        method,
        credentials: 'include',
        cache: 'no-store',
        redirect: 'error',
        headers: { Accept: 'application/json' },
      })
    let response = await send()
    if (response.status === 401) {
      await response.body?.cancel()
      await authentication.refresh()
      response = await send()
    }
    const payload: unknown = await response.json()
    if (!response.ok) throw new ApiResponseError(response.status, apiErrorSchema.parse(payload))
    return payload
  }
  const courses = useQuery({
    queryKey: ['staff-testing-courses', principal.accountId],
    queryFn: async () => staffTestingCoursesSchema.parse(await request('courses')),
  })
  const enter = useMutation({
    mutationFn: async (courseId?: string) => {
      z.object({ ready: z.literal(true) }).parse(await request('session', 'POST'))
      const target = view === 'news' ? '/student/news' : '/student/tasks'
      window.location.assign(courseId ? `${target}?course=${encodeURIComponent(courseId)}` : target)
    },
  })
  return (
    <PageLayout
      title={
        view === 'news'
          ? t`Новости для школьников`
          : view === 'courses'
            ? t`Доступные курсы`
            : t`Занятия — тестирование`
      }
    >
      <p>
        <Trans>
          Откроется настоящий кабинет школьника с вашей тестовой учётной записью. Можно сдавать
          ответы и фотографии, получать и исправлять вердикты. Эти работы не входят в общую
          статистику.
        </Trans>
      </p>
      <p className="text-small text-muted-foreground">
        <Trans>
          Текущий вход в кабинет школьника в этом браузере будет заменён. Вход в Staff сохранится.
          Перед входом завершите отправки и закройте другие вкладки кабинета школьника.
        </Trans>
      </p>
      {courses.isPending ? (
        <p role="status">
          <Trans>Загружаем доступные курсы…</Trans>
        </p>
      ) : null}
      {courses.error || enter.error ? (
        <p role="alert">{(courses.error ?? enter.error)?.message}</p>
      ) : null}
      {courses.error ? (
        <Button onClick={() => void courses.refetch()}>
          <Trans>Повторить</Trans>
        </Button>
      ) : null}
      {courses.data?.courses.length === 0 ? (
        <p>
          <Trans>Вам пока не назначены активные курсы и группы.</Trans>
        </p>
      ) : null}
      {view === 'news' && courses.data?.courses.length ? (
        <Button disabled={enter.isPending} onClick={() => enter.mutate(undefined)}>
          <Trans>Читать новости как школьник</Trans>
        </Button>
      ) : null}
      <div className="grid gap-4">
        {courses.data?.courses.map((course) => (
          <Card key={course.courseId}>
            <CardHeader>
              <CardTitle>{course.name}</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-3">
              <p>{course.groups.map((group) => group.name).join(' · ')}</p>
              <Button disabled={enter.isPending} onClick={() => enter.mutate(course.courseId)}>
                <Trans>Открыть как школьник</Trans>
              </Button>
            </CardContent>
          </Card>
        ))}
      </div>
    </PageLayout>
  )
}
