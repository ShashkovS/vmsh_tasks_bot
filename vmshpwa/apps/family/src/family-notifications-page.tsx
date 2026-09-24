import { t } from '@lingui/core/macro'
import { Trans } from '@lingui/react/macro'
import { currentLocale, dateTimeFormat } from '@vmsh/i18n'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Bell, Volume2 } from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, type ReactNode } from 'react'

import {
  PageLayout,
  PageSection,
  PageStatePanel,
  createNotificationClient,
  useAuthenticatedPrincipal,
  useAuthentication,
  useNotificationEventsQuery,
  useNotificationPreferencesQuery,
  usePushDevice,
  usePushSubscriptionConfigQuery,
} from '@vmsh/app-shell'
import {
  notificationQueryKeys,
  type NotificationEvent,
  type NotificationEventListResponse,
  type NotificationPreference,
} from '@vmsh/contracts'
import { NotificationEventCard, PushDeviceControls } from '@vmsh/product'
import {
  Alert,
  AlertContent,
  AlertDescription,
  AlertTitle,
  Card,
  CardContent,
  Switch,
} from '@vmsh/ui'

type FamilyNotificationCategory =
  | 'lesson_published'
  | 'hint_published'
  | 'solution_published'
  | 'review_completed'
  | 'deadline'
  | 'news'
  | 'group_announcement'
  | 'thread_updated'

// Per dev/development-plan/12-phase-8-news-and-notifications.md,
// ``review_completed`` means one explicit lesson digest for Family; the server
// never creates per-problem Family review events.
const familyCategories: readonly FamilyNotificationCategory[] = [
  'lesson_published',
  'hint_published',
  'solution_published',
  'review_completed',
  'deadline',
  'news',
  'group_announcement',
  'thread_updated',
] as const

function categoryCopy(category: FamilyNotificationCategory): {
  title: string
  description: string
} {
  switch (category) {
    case 'thread_updated':
      return { title: t`Ответ организаторов`, description: t`Ответ в вашем личном обращении` }
    case 'lesson_published':
      return { title: t`Новый урок`, description: t`Условия нового занятия` }
    case 'hint_published':
      return { title: t`Подсказки`, description: t`Опубликованы подсказки к задачам` }
    case 'solution_published':
      return { title: t`Решения`, description: t`Опубликованы решения занятия` }
    case 'review_completed':
      return { title: t`Итоги занятия`, description: t`Один итог после завершения всей проверки` }
    case 'deadline':
      return { title: t`Дедлайн`, description: t`Напоминание о публикации решений` }
    case 'news':
      return { title: t`Новости`, description: t`Публикации кружка` }
    case 'group_announcement':
      return { title: t`Объявление`, description: t`Сообщение для группы ребёнка` }
  }
}

type FamilyNotificationPreference = NotificationPreference & {
  category: FamilyNotificationCategory
}

function isFamilyPreference(
  preference: NotificationPreference,
): preference is FamilyNotificationPreference {
  return familyCategories.includes(preference.category as FamilyNotificationCategory)
}

export function FamilyNotificationSettingsView({
  error = false,
  events,
  eventsError = false,
  eventsLoading = false,
  loading = false,
  onEventsRetry,
  onRead,
  onRetry,
  onToggle,
  pending = false,
  preferences,
  pushControls,
}: {
  error?: boolean
  events?: NotificationEvent[]
  eventsError?: boolean
  eventsLoading?: boolean
  loading?: boolean
  onEventsRetry?: () => void
  onRead?: (eventId: string) => void
  onRetry?: () => void
  onToggle?: (preference: NotificationPreference, enabled: boolean) => void
  pending?: boolean
  preferences?: NotificationPreference[]
  pushControls?: ReactNode
}) {
  const visiblePreferences = preferences?.filter(isFamilyPreference)
  return (
    <PageLayout
      description={t`Новости и материалы всегда остаются в кабинете. Push можно настроить отдельно.`}
      eyebrow={t`Профиль`}
      title={t`Уведомления`}
    >
      <PageSection title={t`Последние события`}>
        {eventsLoading ? <PageStatePanel state="loading" /> : null}
        {eventsError ? (
          <PageStatePanel actionLabel={t`Повторить`} onAction={onEventsRetry} state="error" />
        ) : null}
        {events?.length === 0 ? (
          <PageStatePanel
            description={t`Новые материалы, новости и итог занятия появятся здесь.`}
            state="empty"
            title={t`Пока пусто`}
          />
        ) : null}
        <div className="space-y-2">
          {events?.map((event) => (
            <VisibleFamilyNotification
              event={event}
              key={event.eventId}
              {...(onRead ? { onRead } : {})}
            />
          ))}
        </div>
      </PageSection>
      <PageSection title={t`На этом устройстве`}>{pushControls}</PageSection>
      <PageSection
        description={t`Отдельные push о каждой проверенной задаче ребёнка родителю не отправляются.`}
        title={t`Категории`}
      >
        {loading ? <PageStatePanel state="loading" /> : null}
        {error ? <PageStatePanel actionLabel={t`Повторить`} onAction={onRetry} state="error" /> : null}
        {visiblePreferences ? (
          <Card>
            <CardContent className="divide-y divide-border pt-1">
              {visiblePreferences.map((preference) => {
                const copy = categoryCopy(preference.category)
                return (
                  <div
                    className="flex items-center justify-between gap-4 py-3"
                    key={preference.category}
                  >
                    <div>
                      <p className="text-small font-medium">{copy.title}</p>
                      <p className="text-caption text-muted-foreground">{copy.description}</p>
                    </div>
                    <Switch
                      aria-label={t`Push: ${copy.title}`}
                      checked={preference.pushEnabled}
                      disabled={pending}
                      onCheckedChange={(enabled) => onToggle?.(preference, enabled)}
                    />
                  </div>
                )
              })}
            </CardContent>
          </Card>
        ) : null}
        <Alert tone="neutral">
          <Volume2 aria-hidden="true" />
          <AlertContent>
            <AlertTitle><Trans>Звук только с 9:00 до 21:00</Trans></AlertTitle>
            <AlertDescription>
              <Trans>Ночью новые события остаются видны, но не будят вас.</Trans>
            </AlertDescription>
          </AlertContent>
        </Alert>
      </PageSection>
    </PageLayout>
  )
}

function formatMoment(value: string): string {
  return dateTimeFormat(currentLocale(), {
    day: 'numeric',
    month: 'long',
    hour: '2-digit',
    minute: '2-digit',
    timeZone: 'Europe/Moscow',
  }).format(new Date(value))
}

function familyEventCopy(event: NotificationEvent): { title: string; description: string } {
  if (event.category === 'review_completed' && event.payload.kind === 'family_lesson_digest') {
    const lesson = event.payload.lessonNumber
    const group = event.payload.groupName
    return {
      title: t`Итоги занятия готовы`,
      description:
        typeof lesson === 'number' && typeof group === 'string'
          ? t`${group} · занятие ${lesson}`
          : t`Результаты ребёнка уже доступны в кабинете`,
    }
  }
  const preference = categoryCopy(event.category as FamilyNotificationCategory)
  return preference ?? { title: t`Новое событие`, description: t`Откройте кабинет` }
}

function VisibleFamilyNotification({
  event,
  onRead,
}: {
  event: NotificationEvent
  onRead?: (eventId: string) => void
}) {
  const containerRef = useRef<HTMLDivElement>(null)
  const sentRef = useRef(false)
  useEffect(() => {
    if (event.readAt !== null || sentRef.current || !containerRef.current || !onRead) return
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

  const copy = familyEventCopy(event)
  return (
    <div ref={containerRef}>
      <NotificationEventCard
        description={copy.description}
        href={event.route}
        occurredAt={formatMoment(event.occurredAt)}
        occurredAtDateTime={event.occurredAt}
        title={copy.title}
        unread={event.readAt === null}
      />
    </div>
  )
}

function FamilyPushDeviceSettings({
  applicationServerKey,
  client,
}: {
  applicationServerKey: string
  client: ReturnType<typeof createNotificationClient>
}) {
  const push = usePushDevice({ applicationServerKey, client })
  return (
    <PushDeviceControls
      categories={[
        { id: 'materials', label: t`Новые материалы` },
        { id: 'results', label: t`Итоги занятия` },
        { id: 'deadline', label: t`Дедлайн` },
        { id: 'news', label: t`Новости кружка` },
        { id: 'group_announcement', label: t`Объявления группы` },
      ]}
      onDisable={() => void push.disable()}
      onDismiss={push.dismiss}
      onEnable={() => void push.enable()}
      state={push.state}
    />
  )
}

/** Real Family notification settings; see development-plan Phase 8. */
export function FamilyNotificationsPage() {
  const authentication = useAuthentication()
  const principal = useAuthenticatedPrincipal()
  if (principal.audience !== 'family') throw new Error('Family notifications require Family auth')
  const scope = { audience: 'family' as const, accountId: principal.accountId }
  const client = useMemo(
    () =>
      createNotificationClient(authentication.client.runtime, 'family', {
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
    onError: (error) => authentication.handleApiError(error),
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

  let pushControls: ReactNode
  if (pushConfig.isPending) {
    pushControls = <PageStatePanel state="loading" />
  } else if (pushConfig.error) {
    pushControls = (
      <PageStatePanel
        actionLabel={t`Повторить`}
        onAction={() => void pushConfig.refetch()}
        state="error"
      />
    )
  } else if (pushConfig.data?.enabled && pushConfig.data.applicationServerKey) {
    pushControls = (
      <FamilyPushDeviceSettings
        applicationServerKey={pushConfig.data.applicationServerKey}
        client={client}
      />
    )
  } else {
    pushControls = (
      <Alert tone="neutral">
        <Bell aria-hidden="true" />
        <AlertContent>
          <AlertTitle><Trans>Push пока недоступны</Trans></AlertTitle>
          <AlertDescription><Trans>Новые материалы всё равно будут видны в кабинете.</Trans></AlertDescription>
        </AlertContent>
      </Alert>
    )
  }

  return (
    <FamilyNotificationSettingsView
      error={preferences.isError || preferenceMutation.isError}
      {...(events.data ? { events: events.data.items } : {})}
      eventsError={events.isError || readMutation.isError}
      eventsLoading={events.isPending}
      loading={preferences.isPending}
      onEventsRetry={() => {
        readMutation.reset()
        void events.refetch()
      }}
      onRead={onRead}
      onRetry={() => void preferences.refetch()}
      onToggle={(preference, pushEnabled) =>
        preferenceMutation.mutate({ ...preference, pushEnabled })
      }
      pending={preferenceMutation.isPending}
      {...(preferences.data ? { preferences: preferences.data.items } : {})}
      pushControls={pushControls}
    />
  )
}
