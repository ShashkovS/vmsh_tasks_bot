import { useMemo, useState } from 'react'

import {
  PageLayout,
  PageSection,
  PageStatePanel,
  PublishedClassroomNetworkError,
  bannerDismissalId,
  createGroupBannerClient,
  createFamilyClassroomAssignmentClient,
  useActiveGroupBannersQuery,
  useAuthenticatedPrincipal,
  useAuthentication,
  useBannerDismissals,
  usePublishedClassroomAssignmentsQuery,
} from '@vmsh/app-shell'
import { ClassroomAssignmentStatus, GroupBanner } from '@vmsh/product'

function formatMoment(value: string | null): string | undefined {
  if (value === null) return undefined
  return new Intl.DateTimeFormat('ru-RU', {
    day: 'numeric',
    month: 'long',
    hour: '2-digit',
    minute: '2-digit',
    timeZone: 'Europe/Moscow',
  }).format(new Date(value))
}

/** Authenticated Family home for the child-visible Phase-7 classroom projection. */
export function FamilyHomePage() {
  const authentication = useAuthentication()
  const principal = useAuthenticatedPrincipal()
  if (principal.audience !== 'family') {
    throw new Error('Family home requires a Family principal')
  }
  const defaultChild =
    principal.linkedChildren.find((child) => child.isPrimary)?.studentId ??
    principal.linkedChildren[0]?.studentId ??
    ''
  const [selectedChildId, setSelectedChildId] = useState(defaultChild)
  const selectedChild = principal.linkedChildren.find(
    (child) => child.studentId === selectedChildId,
  )
  const client = useMemo(
    () =>
      createFamilyClassroomAssignmentClient(
        authentication.client.runtime,
        selectedChildId || 'missing',
        {
          refreshSession: async () => {
            try {
              return await authentication.refresh()
            } catch (error) {
              authentication.handleApiError(error)
              throw error
            }
          },
        },
      ),
    [authentication, selectedChildId],
  )
  const query = usePublishedClassroomAssignmentsQuery(
    client,
    { audience: 'family', accountId: principal.accountId },
    selectedChildId || undefined,
    selectedChildId.length > 0,
  )
  const principalScope = { audience: 'family' as const, accountId: principal.accountId }
  const bannerClient = useMemo(
    () =>
      createGroupBannerClient(authentication.client.runtime, 'family', {
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
  const bannerQuery = useActiveGroupBannersQuery(bannerClient, principalScope)
  const bannerDismissals = useBannerDismissals(principalScope)

  return (
    <PageLayout
      actions={
        principal.linkedChildren.length > 1 ? (
          <label className="flex items-center gap-2 text-small font-medium">
            <span>Ребёнок</span>
            <select
              className="min-h-9 rounded-md border border-input bg-surface px-3"
              onChange={(event) => setSelectedChildId(event.target.value)}
              value={selectedChildId}
            >
              {principal.linkedChildren.map((child) => (
                <option key={child.studentId} value={child.studentId}>
                  {child.displayName}
                </option>
              ))}
            </select>
          </label>
        ) : undefined
      }
      description="Семья видит то же подтверждённое распределение, что и школьник."
      eyebrow={selectedChild?.displayName ?? 'Семейный кабинет'}
      title="Текущие занятия"
    >
      {bannerQuery.data ? (
        <div className="space-y-2" aria-label="Объявления">
          {bannerQuery.data.items
            .filter((banner) => !bannerDismissals.dismissed.has(bannerDismissalId(banner)))
            .map((banner) => (
              <GroupBanner
                banner={banner}
                key={banner.bannerId}
                onDismiss={() => bannerDismissals.dismiss(banner)}
              />
            ))}
        </div>
      ) : null}
      <PageSection
        description="Черновики распределения и данные других школьников здесь не показываются."
        title="Очные занятия"
      >
        {selectedChildId.length === 0 ? (
          <PageStatePanel
            description="Обратитесь к администратору кружка, чтобы связать аккаунт с ребёнком."
            state="empty"
            title="Нет доступного профиля ребёнка"
          />
        ) : null}
        {query.isPending && selectedChildId ? <PageStatePanel state="loading" /> : null}
        {query.error ? (
          <PageStatePanel
            actionLabel="Повторить"
            onAction={() => void query.refetch()}
            state={query.error instanceof PublishedClassroomNetworkError ? 'offline' : 'error'}
          />
        ) : null}
        {query.data?.items.length === 0 ? (
          <PageStatePanel
            description="Когда администратор добавит группу в очное событие, оно появится здесь."
            state="empty"
            title="Очные занятия пока не запланированы"
          />
        ) : null}
        <div className="grid gap-3 lg:grid-cols-2">
          {query.data?.items.map((item) => {
            const announcedAt = formatMoment(item.announcedAt)
            const confirmedAt = formatMoment(item.confirmedAt)
            return (
              <div className="space-y-2" key={`${item.eventPublicId}:${item.coursePublicId}`}>
                <p className="text-small font-medium text-foreground">
                  {item.courseName} · {item.eventName}
                </p>
                <ClassroomAssignmentStatus
                  {...(announcedAt ? { announcedAt } : {})}
                  audience="family"
                  {...(item.classroomName ? { classroomName: item.classroomName } : {})}
                  {...(confirmedAt ? { confirmedAt } : {})}
                  status={item.status}
                  {...(selectedChild ? { studentName: selectedChild.displayName } : {})}
                />
              </div>
            )
          })}
        </div>
      </PageSection>
    </PageLayout>
  )
}
