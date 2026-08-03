import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Bell, Volume2 } from 'lucide-react'
import { useMemo, type ReactNode } from 'react'

import {
  PageLayout,
  PageSection,
  PageStatePanel,
  createNotificationClient,
  useAuthenticatedPrincipal,
  useAuthentication,
  useNotificationPreferencesQuery,
  usePushDevice,
  usePushSubscriptionConfigQuery,
} from '@vmsh/app-shell'
import { notificationQueryKeys, type NotificationPreference } from '@vmsh/contracts'
import { PushDeviceControls } from '@vmsh/product'
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
  'lesson_published' | 'hint_published' | 'solution_published' | 'deadline' | 'news'

// Phase 8 sends Family shared materials/news, not per-review, oral or classroom
// pushes. Course overrides remain Student-only at the API boundary.
const familyCategories: readonly FamilyNotificationCategory[] = [
  'lesson_published',
  'hint_published',
  'solution_published',
  'deadline',
  'news',
] as const

const categoryCopy: Record<FamilyNotificationCategory, { title: string; description: string }> = {
  lesson_published: { title: 'Новый урок', description: 'Условия нового занятия' },
  hint_published: { title: 'Подсказки', description: 'Опубликованы подсказки к задачам' },
  solution_published: { title: 'Решения', description: 'Опубликованы решения занятия' },
  deadline: { title: 'Дедлайн', description: 'Напоминание о публикации решений' },
  news: { title: 'Новости', description: 'Публикации кружка' },
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
  loading = false,
  onRetry,
  onToggle,
  pending = false,
  preferences,
  pushControls,
}: {
  error?: boolean
  loading?: boolean
  onRetry?: () => void
  onToggle?: (preference: NotificationPreference, enabled: boolean) => void
  pending?: boolean
  preferences?: NotificationPreference[]
  pushControls?: ReactNode
}) {
  const visiblePreferences = preferences?.filter(isFamilyPreference)
  return (
    <PageLayout
      description="Новости и материалы всегда остаются в кабинете. Push можно настроить отдельно."
      eyebrow="Профиль"
      title="Уведомления"
    >
      <PageSection title="На этом устройстве">{pushControls}</PageSection>
      <PageSection
        description="Отдельные push о каждой проверенной задаче ребёнка семье не отправляются."
        title="Категории"
      >
        {loading ? <PageStatePanel state="loading" /> : null}
        {error ? <PageStatePanel actionLabel="Повторить" onAction={onRetry} state="error" /> : null}
        {visiblePreferences ? (
          <Card>
            <CardContent className="divide-y divide-border pt-1">
              {visiblePreferences.map((preference) => {
                const copy = categoryCopy[preference.category]
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
                      aria-label={`Push: ${copy.title}`}
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
            <AlertTitle>Звук только с 9:00 до 21:00</AlertTitle>
            <AlertDescription>
              Ночью новые события остаются видны, но не будят вас.
            </AlertDescription>
          </AlertContent>
        </Alert>
      </PageSection>
    </PageLayout>
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
        { id: 'materials', label: 'Новые материалы' },
        { id: 'deadline', label: 'Дедлайн' },
        { id: 'news', label: 'Новости кружка' },
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

  let pushControls: ReactNode
  if (pushConfig.isPending) {
    pushControls = <PageStatePanel state="loading" />
  } else if (pushConfig.error) {
    pushControls = (
      <PageStatePanel
        actionLabel="Повторить"
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
          <AlertTitle>Push пока недоступны</AlertTitle>
          <AlertDescription>Новые материалы всё равно будут видны в кабинете.</AlertDescription>
        </AlertContent>
      </Alert>
    )
  }

  return (
    <FamilyNotificationSettingsView
      error={preferences.isError || preferenceMutation.isError}
      loading={preferences.isPending}
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
