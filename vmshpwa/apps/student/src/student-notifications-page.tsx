import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Bell, Volume2 } from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef } from 'react'

import {
  PageLayout,
  PageSection,
  PageStatePanel,
  createNotificationClient,
  useAuthenticatedPrincipal,
  useAuthentication,
  useNotificationEventsQuery,
  useNotificationPreferencesQuery,
} from '@vmsh/app-shell'
import {
  notificationQueryKeys,
  type NotificationCategory,
  type NotificationEvent,
  type NotificationEventListResponse,
  type NotificationPreference,
} from '@vmsh/contracts'
import { NotificationEventCard } from '@vmsh/product'
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
  const preferences = useNotificationPreferencesQuery(client, scope)
  const events = useNotificationEventsQuery(client, scope)
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

  return (
    <PageLayout
      description="Новые события всегда остаются в кабинете. Push и звук можно настроить отдельно."
      eyebrow="Профиль"
      title="Уведомления"
    >
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
