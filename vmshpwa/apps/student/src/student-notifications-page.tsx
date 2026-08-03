import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Bell, Volume2 } from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import {
  PageLayout,
  PageSection,
  PageStatePanel,
  createNotificationClient,
  createStudentCourseClient,
  useAuthenticatedPrincipal,
  useAuthentication,
  useCourseNotificationPreferencesQuery,
  useNotificationEventsQuery,
  useNotificationPreferencesQuery,
  usePushSubscriptionConfigQuery,
  usePushDevice,
  useStudentCoursesQuery,
} from '@vmsh/app-shell'
import {
  notificationQueryKeys,
  type NotificationCategory,
  type NotificationEvent,
  type NotificationEventListResponse,
  type NotificationPreference,
} from '@vmsh/contracts'
import {
  CourseContext,
  CourseNotificationSettings,
  NotificationEventCard,
  PushDeviceControls,
  type CourseView,
} from '@vmsh/product'
import {
  Alert,
  AlertContent,
  AlertDescription,
  AlertTitle,
  Card,
  CardContent,
  Switch,
} from '@vmsh/ui'

const categoryCopy: Record<NotificationCategory, { title: string; description: string }> = {
  lesson_published: { title: 'Новый урок', description: 'Условия нового занятия' },
  hint_published: { title: 'Опубликована подсказка', description: 'Подсказки к задачам' },
  solution_published: { title: 'Опубликованы решения', description: 'Решения задач занятия' },
  review_completed: {
    title: 'Проверка завершена',
    description: 'Результаты письменной проверки',
  },
  thread_updated: { title: 'Новое сообщение', description: 'Обсуждение решения или вопроса' },
  oral_window: { title: 'Устный приём', description: 'Открытие окна устной сдачи' },
  classroom_assignment: { title: 'Назначена аудитория', description: 'Очное занятие' },
  deadline: { title: 'Скоро дедлайн', description: 'Напоминание о публикации решений' },
  news: { title: 'Новая публикация', description: 'Новости кружка' },
}

function eventDescription(event: NotificationEvent): string {
  if (event.category === 'review_completed') {
    const count = event.payload.count
    if (typeof count === 'number' && Number.isInteger(count) && count > 1) {
      return `Проверено задач: ${count}`
    }
  }
  if (event.category !== 'classroom_assignment') return categoryCopy[event.category].description
  const values = ['courseName', 'groupName', 'classroomName'].map((key) => event.payload[key])
  return values.filter((value): value is string => typeof value === 'string').join(' · ')
}

function formatMoment(value: string): string {
  return new Intl.DateTimeFormat('ru-RU', {
    day: 'numeric',
    month: 'long',
    hour: '2-digit',
    minute: '2-digit',
    timeZone: 'Europe/Moscow',
  }).format(new Date(value))
}

export function VisibleNotification({
  event,
  onRead,
}: {
  event: NotificationEvent
  onRead: (eventId: string) => void
}) {
  const containerRef = useRef<HTMLDivElement>(null)
  const sentRef = useRef(false)

  useEffect(() => {
    if (event.readAt !== null || sentRef.current || !containerRef.current) return
    if (typeof IntersectionObserver === 'undefined') return
    let visible = false
    let timer: ReturnType<typeof setTimeout> | undefined
    const cancel = () => {
      if (timer !== undefined) clearTimeout(timer)
      timer = undefined
    }
    const updateTimer = () => {
      cancel()
      if (!visible || document.visibilityState !== 'visible' || sentRef.current) return
      timer = setTimeout(() => {
        sentRef.current = true
        onRead(event.eventId)
      }, 3_000)
    }
    const observer = new IntersectionObserver(
      ([entry]) => {
        visible = Boolean(entry?.isIntersecting && entry.intersectionRatio >= 0.75)
        updateTimer()
      },
      { threshold: [0.75] },
    )
    observer.observe(containerRef.current)
    document.addEventListener('visibilitychange', updateTimer)
    return () => {
      cancel()
      observer.disconnect()
      document.removeEventListener('visibilitychange', updateTimer)
    }
  }, [event.eventId, event.readAt, onRead])

  return (
    <div ref={containerRef}>
      <NotificationEventCard
        description={eventDescription(event)}
        href={event.route}
        occurredAt={formatMoment(event.occurredAt)}
        occurredAtDateTime={event.occurredAt}
        title={categoryCopy[event.category].title}
        unread={event.readAt === null}
      />
    </div>
  )
}

export function PushDeviceSettings({
  client,
  applicationServerKey,
}: {
  client: ReturnType<typeof createNotificationClient>
  applicationServerKey: string
}) {
  const push = usePushDevice({ applicationServerKey, client })
  return (
    <PushDeviceControls
      categories={[
        { id: 'review', label: 'Результат проверки' },
        { id: 'deadline', label: 'Дедлайн и новые материалы' },
        { id: 'news', label: 'Новости кружка' },
      ]}
      onDisable={() => void push.disable()}
      onDismiss={push.dismiss}
      onEnable={() => void push.enable()}
      state={push.state}
    />
  )
}

/** Real Student notification settings and account-scoped in-app event list. */
export function StudentNotificationsPage() {
  const authentication = useAuthentication()
  const principal = useAuthenticatedPrincipal()
  if (principal.audience !== 'student')
    throw new Error('Student notifications require Student auth')
  const scope = { audience: 'student' as const, accountId: principal.accountId }
  const client = useMemo(
    () =>
      createNotificationClient(authentication.client.runtime, 'student', {
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
  const courseClient = useMemo(
    () =>
      createStudentCourseClient(authentication.client.runtime, {
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
  const courses = useStudentCoursesQuery(courseClient, scope)
  const [requestedCourseId, setRequestedCourseId] = useState<string>()
  const availableCourses = courses.data?.enrollments ?? []
  const courseId = availableCourses.some((item) => item.course.courseId === requestedCourseId)
    ? requestedCourseId
    : availableCourses[0]?.course.courseId
  const preferences = useNotificationPreferencesQuery(client, scope)
  const coursePreferences = useCourseNotificationPreferencesQuery(client, scope, courseId)
  const events = useNotificationEventsQuery(client, scope)
  const pushConfig = usePushSubscriptionConfigQuery(client, scope)
  const queryClient = useQueryClient()
  const preferenceMutation = useMutation({
    mutationFn: (preference: NotificationPreference) =>
      client.updatePreference({
        schemaVersion: 1,
        category: preference.category,
        inAppEnabled: preference.inAppEnabled,
        pushEnabled: preference.pushEnabled,
        soundEnabled: preference.soundEnabled,
        quietStartsLocal: preference.quietStartsLocal,
        quietEndsLocal: preference.quietEndsLocal,
        timezone: preference.timezone,
      }),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: notificationQueryKeys.preferences(scope) }),
  })
  const coursePreferenceMutation = useMutation({
    mutationFn: ({
      selectedCourseId,
      category,
      pushEnabled,
    }: {
      selectedCourseId: string
      category: NotificationCategory
      pushEnabled: boolean | null
    }) =>
      client.updateCoursePreference(selectedCourseId, {
        schemaVersion: 1,
        category,
        pushEnabled,
      }),
    onSuccess: (_response, variables) =>
      queryClient.invalidateQueries({
        queryKey: notificationQueryKeys.coursePreferences(scope, variables.selectedCourseId),
      }),
  })
  const readMutation = useMutation({
    mutationFn: (eventId: string) => client.acknowledge(eventId),
    onSuccess: (receipt) => {
      queryClient.setQueryData<NotificationEventListResponse>(
        notificationQueryKeys.events(scope),
        (current) =>
          current && {
            ...current,
            items: current.items.map((item) =>
              item.eventId === receipt.eventId ? { ...item, readAt: receipt.readAt } : item,
            ),
          },
      )
    },
  })
  const markRead = readMutation.mutate
  const onRead = useCallback((eventId: string) => markRead(eventId), [markRead])
  const courseViews: CourseView[] = (courses.data?.enrollments ?? []).map(({ course }, index) => ({
    id: course.courseId,
    code: course.code,
    name: course.name,
    subjectCode: course.subjectCode,
    accentIndex: Math.min(4, index + 1) as CourseView['accentIndex'],
  }))
  const selectedCourse = courseViews.find((course) => course.id === courseId)

  return (
    <PageLayout
      description="Новые события всегда остаются в кабинете. Push и звук можно настроить отдельно."
      eyebrow="Профиль"
      title="Уведомления"
    >
      {pushConfig.data?.enabled && pushConfig.data.applicationServerKey ? (
        <PageSection title="На этом устройстве">
          <PushDeviceSettings
            applicationServerKey={pushConfig.data.applicationServerKey}
            client={client}
          />
        </PageSection>
      ) : null}
      <PageSection title="Категории">
        {preferences.isPending ? <PageStatePanel state="loading" /> : null}
        {preferences.error ? (
          <PageStatePanel
            actionLabel="Повторить"
            onAction={() => void preferences.refetch()}
            state="error"
          />
        ) : null}
        {preferences.data ? (
          <Card>
            <CardContent className="divide-y divide-border pt-1">
              {preferences.data.items.map((preference) => (
                <div
                  className="flex items-center justify-between gap-4 py-3"
                  key={preference.category}
                >
                  <div>
                    <p className="text-small font-medium">
                      {categoryCopy[preference.category].title}
                    </p>
                    <p className="text-caption text-muted-foreground">
                      {categoryCopy[preference.category].description}
                    </p>
                  </div>
                  <Switch
                    aria-label={`Push: ${categoryCopy[preference.category].title}`}
                    checked={preference.pushEnabled}
                    disabled={preferenceMutation.isPending}
                    onCheckedChange={(pushEnabled) =>
                      preferenceMutation.mutate({ ...preference, pushEnabled })
                    }
                  />
                </div>
              ))}
            </CardContent>
          </Card>
        ) : null}
        {preferenceMutation.error ? (
          <Alert tone="danger">
            <Bell aria-hidden="true" />
            <AlertContent>
              <AlertTitle>Настройка не сохранена</AlertTitle>
              <AlertDescription>Проверьте соединение и попробуйте ещё раз.</AlertDescription>
            </AlertContent>
          </Alert>
        ) : null}
        <Alert tone="neutral">
          <Volume2 aria-hidden="true" />
          <AlertContent>
            <AlertTitle>Звук только с 9:00 до 21:00</AlertTitle>
            <AlertDescription>
              Ночью новые события видны в приложении, но не будят вас.
            </AlertDescription>
          </AlertContent>
        </Alert>
      </PageSection>

      {selectedCourse ? (
        <PageSection title="По курсам">
          {courseViews.length > 1 ? (
            <CourseContext
              activeCourseId={selectedCourse.id}
              courses={courseViews}
              onCourseChange={setRequestedCourseId}
            />
          ) : null}
          {coursePreferences.isPending ? <PageStatePanel state="loading" /> : null}
          {coursePreferences.error ? (
            <PageStatePanel
              actionLabel="Повторить"
              onAction={() => void coursePreferences.refetch()}
              state="error"
            />
          ) : null}
          {coursePreferences.data ? (
            <CourseNotificationSettings
              onReset={(selectedCourseId, category) =>
                coursePreferenceMutation.mutate({
                  selectedCourseId,
                  category: category as NotificationCategory,
                  pushEnabled: null,
                })
              }
              onToggle={(selectedCourseId, category, pushEnabled) =>
                coursePreferenceMutation.mutate({
                  selectedCourseId,
                  category: category as NotificationCategory,
                  pushEnabled,
                })
              }
              preferences={coursePreferences.data.items.map((preference) => ({
                course: selectedCourse,
                category: preference.category,
                label: categoryCopy[preference.category].title,
                enabled: preference.pushEnabled,
                inherited: preference.inherited,
              }))}
            />
          ) : null}
          {coursePreferenceMutation.error ? (
            <Alert tone="danger">
              <Bell aria-hidden="true" />
              <AlertContent>
                <AlertTitle>Настройка курса не сохранена</AlertTitle>
                <AlertDescription>Проверьте соединение и попробуйте ещё раз.</AlertDescription>
              </AlertContent>
            </Alert>
          ) : null}
        </PageSection>
      ) : null}

      <PageSection title="Последние события">
        {events.isPending ? <PageStatePanel state="loading" /> : null}
        {events.error ? (
          <PageStatePanel
            actionLabel="Повторить"
            onAction={() => void events.refetch()}
            state="error"
          />
        ) : null}
        {events.data?.items.length === 0 ? (
          <PageStatePanel
            description="Новые события появятся здесь."
            state="empty"
            title="Пока пусто"
          />
        ) : null}
        <div className="space-y-2">
          {events.data?.items.map((event) => (
            <VisibleNotification event={event} key={event.eventId} onRead={onRead} />
          ))}
        </div>
      </PageSection>
    </PageLayout>
  )
}
