import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useEffect, useMemo, useState, type FormEvent } from 'react'

import {
  PageLayout,
  PageSection,
  PageStatePanel,
  createStaffGroupBannerClient,
  createTelegramBindingClient,
  useAuthenticatedPrincipal,
  useAuthentication,
  useStaffGroupBannersQuery,
  useTelegramBindingOwnersQuery,
} from '@vmsh/app-shell'
import {
  ApiResponseError,
  groupBannerQueryKeys,
  type GroupBanner as GroupBannerData,
  type GroupBannerAudience,
} from '@vmsh/contracts'
import { GroupBanner } from '@vmsh/product'
import {
  Alert,
  AlertContent,
  AlertDescription,
  AlertTitle,
  Button,
  Card,
  CardContent,
  Checkbox,
  Input,
  Label,
  Textarea,
} from '@vmsh/ui'

type Draft = {
  groupId: string
  audience: GroupBannerAudience
  html: string
  startsAt: string
  endsAt: string
  priority: string
  dismissible: boolean
}

const emptyDraft: Draft = {
  groupId: '',
  audience: 'both',
  html: '',
  startsAt: '',
  endsAt: '',
  priority: '0',
  dismissible: true,
}

function readDraft(accountId: string): Draft {
  try {
    const stored: unknown = JSON.parse(
      globalThis.localStorage.getItem(`vmshpwa:staff:${accountId}:group-banner-draft`) ?? 'null',
    )
    if (!stored || typeof stored !== 'object') return emptyDraft
    return { ...emptyDraft, ...(stored as Partial<Draft>) }
  } catch {
    return emptyDraft
  }
}

function moscowIso(value: string): string {
  return new Date(`${value}:00+03:00`).toISOString()
}

function moscowInput(value: string): string {
  const parts = new Intl.DateTimeFormat('en-CA', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
    timeZone: 'Europe/Moscow',
  }).formatToParts(new Date(value))
  const part = (type: Intl.DateTimeFormatPartTypes) =>
    parts.find((item) => item.type === type)?.value ?? ''
  return `${part('year')}-${part('month')}-${part('day')}T${part('hour')}:${part('minute')}`
}

function errorText(error: Error): string {
  return error instanceof ApiResponseError
    ? error.message
    : 'Проверьте соединение и повторите попытку.'
}

export function StaffGroupBannersPage() {
  const authentication = useAuthentication()
  const principal = useAuthenticatedPrincipal()
  if (principal.audience !== 'staff') throw new Error('Group banners require Staff auth')
  const scope = { audience: 'staff' as const, accountId: principal.accountId }
  const bannerClient = useMemo(
    () =>
      createStaffGroupBannerClient(authentication.client.runtime, {
        refreshSession: () => authentication.refresh(),
      }),
    [authentication],
  )
  const ownerClient = useMemo(
    () =>
      createTelegramBindingClient(authentication.client.runtime, {
        refreshSession: () => authentication.refresh(),
      }),
    [authentication],
  )
  const banners = useStaffGroupBannersQuery(bannerClient, scope)
  const owners = useTelegramBindingOwnersQuery(ownerClient, scope)
  const queryClient = useQueryClient()
  const [draft, setDraft] = useState<Draft>(() => readDraft(principal.accountId))
  const [editing, setEditing] = useState<GroupBannerData | null>(null)

  useEffect(() => {
    globalThis.localStorage.setItem(
      `vmshpwa:staff:${principal.accountId}:group-banner-draft`,
      JSON.stringify(draft),
    )
  }, [draft, principal.accountId])

  const groups =
    owners.data?.courses.flatMap((course) =>
      course.groups
        .filter((group) => group.status === 'active')
        .map((group) => ({
          groupId: group.groupId,
          label: `${course.courseName} · ${group.groupName}`,
          courseId: course.courseId,
          courseName: course.courseName,
          groupName: group.groupName,
        })),
    ) ?? []
  const groupId = draft.groupId || groups[0]?.groupId || ''

  const mutation = useMutation({
    mutationFn: async (command: { kind: 'save' } | { kind: 'cancel'; banner: GroupBannerData }) => {
      if (command.kind === 'cancel') {
        return bannerClient.cancel(command.banner.bannerId, command.banner.version)
      }
      const common = {
        schemaVersion: 1 as const,
        audience: draft.audience,
        html: draft.html,
        startsAt: moscowIso(draft.startsAt),
        endsAt: moscowIso(draft.endsAt),
        priority: Number(draft.priority),
        dismissible: draft.dismissible,
      }
      return editing
        ? bannerClient.update(editing.bannerId, editing.version, common)
        : bannerClient.create({ ...common, groupId })
    },
    onSuccess: async () => {
      setDraft(emptyDraft)
      setEditing(null)
      await queryClient.invalidateQueries({ queryKey: groupBannerQueryKeys.staff(scope) })
    },
    onError: (error) => authentication.handleApiError(error),
  })

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!groupId || !draft.startsAt || !draft.endsAt || !draft.html.trim()) return
    mutation.mutate({ kind: 'save' })
  }

  function beginEdit(banner: GroupBannerData) {
    setEditing(banner)
    setDraft({
      groupId: banner.group.groupId,
      audience: banner.audience,
      html: banner.html,
      startsAt: moscowInput(banner.startsAt),
      endsAt: moscowInput(banner.endsAt),
      priority: String(banner.priority),
      dismissible: banner.dismissible,
    })
    globalThis.scrollTo({ top: 0, behavior: 'smooth' })
  }

  return (
    <PageLayout
      description="Короткие объявления на «Сейчас». Это не массовая рассылка и не публикация в Telegram."
      eyebrow="Admin only"
      title="Объявления"
      width="wide"
    >
      <PageSection title={editing ? 'Изменить объявление' : 'Новое объявление'}>
        {owners.isPending ? <PageStatePanel state="loading" /> : null}
        {owners.error ? <PageStatePanel state="error" /> : null}
        {owners.data ? (
          <Card>
            <CardContent className="pt-4">
              <form className="grid gap-4" onSubmit={submit}>
                <div className="grid gap-3 lg:grid-cols-3">
                  <Label className="grid gap-1">
                    Группа
                    <select
                      className="min-h-10 rounded-md border border-input bg-surface px-3 text-small"
                      disabled={editing !== null}
                      onChange={(event) =>
                        setDraft((value) => ({ ...value, groupId: event.target.value }))
                      }
                      value={groupId}
                    >
                      {groups.map((group) => (
                        <option key={group.groupId} value={group.groupId}>
                          {group.label}
                        </option>
                      ))}
                    </select>
                  </Label>
                  <Label className="grid gap-1">
                    Показывать
                    <select
                      className="min-h-10 rounded-md border border-input bg-surface px-3 text-small"
                      onChange={(event) =>
                        setDraft((value) => ({
                          ...value,
                          audience: event.target.value as GroupBannerAudience,
                        }))
                      }
                      value={draft.audience}
                    >
                      <option value="both">Школьнику и семье</option>
                      <option value="student">Только школьнику</option>
                      <option value="family">Только семье</option>
                    </select>
                  </Label>
                  <Label className="grid gap-1">
                    Приоритет
                    <Input
                      max="100"
                      min="-100"
                      onChange={(event) =>
                        setDraft((value) => ({ ...value, priority: event.target.value }))
                      }
                      type="number"
                      value={draft.priority}
                    />
                  </Label>
                </div>
                <Label className="grid gap-1">
                  Текст · допустимы b, i, a и code
                  <Textarea
                    onChange={(event) =>
                      setDraft((value) => ({ ...value, html: event.target.value }))
                    }
                    placeholder={
                      '<b>Разбор сегодня в 17:00</b> · <a href="https://…">Подключиться</a>'
                    }
                    rows={4}
                    value={draft.html}
                  />
                </Label>
                <div className="grid gap-3 sm:grid-cols-2">
                  <Label className="grid gap-1">
                    Начало показа · Москва
                    <Input
                      onChange={(event) =>
                        setDraft((value) => ({ ...value, startsAt: event.target.value }))
                      }
                      required
                      type="datetime-local"
                      value={draft.startsAt}
                    />
                  </Label>
                  <Label className="grid gap-1">
                    Конец показа · Москва
                    <Input
                      onChange={(event) =>
                        setDraft((value) => ({ ...value, endsAt: event.target.value }))
                      }
                      required
                      type="datetime-local"
                      value={draft.endsAt}
                    />
                  </Label>
                </div>
                <Label className="flex items-center gap-2">
                  <Checkbox
                    checked={draft.dismissible}
                    onCheckedChange={(checked) =>
                      setDraft((value) => ({ ...value, dismissible: checked === true }))
                    }
                  />
                  Можно скрыть на этом устройстве
                </Label>
                <p className="text-caption text-muted-foreground">
                  Безопасный предпросмотр появится в списке после серверной очистки HTML.
                </p>
                <div className="flex flex-wrap gap-2">
                  <Button disabled={mutation.isPending || groups.length === 0} type="submit">
                    {editing ? 'Сохранить изменения' : 'Запланировать'}
                  </Button>
                  {editing ? (
                    <Button
                      onClick={() => {
                        setEditing(null)
                        setDraft(emptyDraft)
                      }}
                      type="button"
                      variant="outline"
                    >
                      Отмена
                    </Button>
                  ) : null}
                </div>
              </form>
            </CardContent>
          </Card>
        ) : null}
        {mutation.error ? (
          <Alert role="alert" tone="danger">
            <AlertContent>
              <AlertTitle>Изменение не сохранено</AlertTitle>
              <AlertDescription>{errorText(mutation.error)}</AlertDescription>
            </AlertContent>
          </Alert>
        ) : null}
      </PageSection>
      <PageSection title="Запланированные и прошлые">
        {banners.isPending ? <PageStatePanel state="loading" /> : null}
        {banners.error ? <PageStatePanel state="error" /> : null}
        {banners.data?.items.length === 0 ? <PageStatePanel state="empty" /> : null}
        <div className="space-y-3">
          {banners.data?.items.map((banner) => (
            <Card key={banner.bannerId}>
              <CardContent className="space-y-3 pt-4">
                <GroupBanner banner={banner} />
                <p className="font-num text-caption text-muted-foreground">
                  {new Intl.DateTimeFormat('ru-RU', {
                    dateStyle: 'short',
                    timeStyle: 'short',
                    timeZone: 'Europe/Moscow',
                  }).format(new Date(banner.startsAt))}{' '}
                  —{' '}
                  {new Intl.DateTimeFormat('ru-RU', {
                    dateStyle: 'short',
                    timeStyle: 'short',
                    timeZone: 'Europe/Moscow',
                  }).format(new Date(banner.endsAt))}
                </p>
                {banner.status === 'active' ? (
                  <div className="flex gap-2">
                    <Button onClick={() => beginEdit(banner)} size="sm" variant="outline">
                      Изменить
                    </Button>
                    <Button
                      onClick={() => mutation.mutate({ kind: 'cancel', banner })}
                      size="sm"
                      variant="ghost"
                    >
                      Отменить
                    </Button>
                  </div>
                ) : (
                  <p className="text-caption text-muted-foreground">Отменено</p>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      </PageSection>
      <Alert tone="info">
        <AlertContent>
          <AlertTitle>Полные рассылки — во второй версии</AlertTitle>
          <AlertDescription>
            Markdown-редактор, preview получателей и произвольная доставка PWA/Telegram здесь пока
            не включены.
          </AlertDescription>
        </AlertContent>
      </Alert>
    </PageLayout>
  )
}
