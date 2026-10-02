import { t } from '@lingui/core/macro'
import { Trans } from '@lingui/react/macro'
import { currentLocale, dateTimeFormat } from '@vmsh/i18n'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { lazy, Suspense, useEffect, useMemo, useState, type FormEvent } from 'react'

import {
  PageLayout,
  PageSection,
  PageStatePanel,
  createStaffGroupBannerClient,
  createStaffRichMediaClient,
  createTelegramBindingClient,
  useAuthenticatedPrincipal,
  useAuthentication,
  useStaffGroupBannersQuery,
  useTelegramBindingOwnersQuery,
} from '@vmsh/app-shell'
import {
  ApiResponseError,
  groupBannerQueryKeys,
  type CommunicationAttendanceMode,
  type GroupBanner as GroupBannerData,
  type GroupBannerAudience,
  type RichDocument,
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
} from '@vmsh/ui'

const RichMarkdownEditor = lazy(() =>
  import('./rich-markdown-editor').then((module) => ({ default: module.RichMarkdownEditor })),
)

type Draft = {
  courseId: string
  groupId: string
  audience: GroupBannerAudience
  attendanceMode: CommunicationAttendanceMode
  markdown: string
  startsAt: string
  endsAt: string
  priority: string
  dismissible: boolean
}

const emptyDraft: Draft = {
  courseId: '',
  groupId: '',
  audience: 'both',
  attendanceMode: 'all',
  markdown: '',
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
    const item = stored as Record<string, unknown>
    return {
      courseId: typeof item.courseId === 'string' ? item.courseId : '',
      groupId: typeof item.groupId === 'string' ? item.groupId : '',
      audience:
        item.audience === 'student' || item.audience === 'family' || item.audience === 'both'
          ? item.audience
          : 'both',
      attendanceMode:
        item.attendanceMode === 'online' || item.attendanceMode === 'in_person'
          ? item.attendanceMode
          : 'all',
      markdown: typeof item.markdown === 'string' ? item.markdown : '',
      startsAt: typeof item.startsAt === 'string' ? item.startsAt : '',
      endsAt: typeof item.endsAt === 'string' ? item.endsAt : '',
      priority: typeof item.priority === 'string' ? item.priority : '0',
      dismissible: typeof item.dismissible === 'boolean' ? item.dismissible : true,
    }
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
    : t`Проверьте соединение и повторите попытку.`
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
  const richMediaClient = useMemo(
    () =>
      createStaffRichMediaClient(authentication.client.runtime, {
        refreshSession: () => authentication.refresh(),
      }),
    [authentication],
  )
  const banners = useStaffGroupBannersQuery(bannerClient, scope)
  const owners = useTelegramBindingOwnersQuery(ownerClient, scope)
  const queryClient = useQueryClient()
  const [draft, setDraft] = useState<Draft>(() => readDraft(principal.accountId))
  const [editing, setEditing] = useState<GroupBannerData | null>(null)
  const [document, setDocument] = useState<RichDocument | null>(null)

  useEffect(() => {
    try {
      globalThis.localStorage.setItem(
        `vmshpwa:staff:${principal.accountId}:group-banner-draft`,
        JSON.stringify(draft),
      )
    } catch {
      // Storage denial must not crash the editor; the visible draft remains in React state.
    }
  }, [draft, principal.accountId])

  const courses = owners.data?.courses.filter((course) => course.status === 'active') ?? []
  const legacyGroupCourseId = courses.find((course) =>
    course.groups.some((group) => group.groupId === draft.groupId),
  )?.courseId
  const courseId = draft.courseId || legacyGroupCourseId || courses[0]?.courseId || ''
  const selectedCourse = courses.find((course) => course.courseId === courseId)
  const groups = selectedCourse?.groups.filter((group) => group.status === 'active') ?? []

  const mutation = useMutation({
    mutationFn: async (command: { kind: 'save' } | { kind: 'cancel'; banner: GroupBannerData }) => {
      if (command.kind === 'cancel') {
        return bannerClient.cancel(command.banner.bannerId, command.banner.version)
      }
      if (document === null) throw new Error('Rich Markdown has not passed validation')
      const common = {
        schemaVersion: 3 as const,
        courseId,
        groupId: draft.groupId || null,
        audience: draft.audience,
        attendanceMode: draft.attendanceMode,
        markdown: draft.markdown,
        document,
        startsAt: moscowIso(draft.startsAt),
        endsAt: moscowIso(draft.endsAt),
        priority: Number(draft.priority),
        dismissible: draft.dismissible,
      }
      return editing
        ? bannerClient.update(editing.bannerId, editing.version, common)
        : bannerClient.create(common)
    },
    onSuccess: async () => {
      setDraft(emptyDraft)
      setEditing(null)
      setDocument(null)
      await queryClient.invalidateQueries({ queryKey: groupBannerQueryKeys.staff(scope) })
    },
    onError: (error) => authentication.handleApiError(error),
  })

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!courseId || !draft.startsAt || !draft.endsAt || document === null) return
    mutation.mutate({ kind: 'save' })
  }

  function beginEdit(banner: GroupBannerData) {
    setEditing(banner)
    setDraft({
      courseId: banner.group.courseId,
      groupId: banner.targetGroupId ?? '',
      audience: banner.audience,
      attendanceMode: banner.attendanceMode,
      markdown: banner.markdown ?? '',
      startsAt: moscowInput(banner.startsAt),
      endsAt: moscowInput(banner.endsAt),
      priority: String(banner.priority),
      dismissible: banner.dismissible,
    })
    setDocument(banner.document ?? null)
    globalThis.scrollTo({ top: 0, behavior: 'smooth' })
  }

  return (
    <PageLayout
      description={t`Короткие сообщения для курса или группы: появятся на «Сейчас» и придут уведомлением на устройства с включёнными push.`}
      eyebrow="Admin only"
      title={t`Рассылки`}
      width="wide"
    >
      <PageSection title={editing ? t`Изменить объявление` : t`Новое объявление`}>
        {owners.isPending ? <PageStatePanel state="loading" /> : null}
        {owners.error ? <PageStatePanel state="error" /> : null}
        {owners.data ? (
          <Card>
            <CardContent className="pt-4">
              <form className="grid gap-4" onSubmit={submit}>
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
                  <Label className="grid gap-1">
                    <Trans>Курс</Trans>
                    <select
                      className="min-h-10 rounded-md border border-input bg-surface px-3 text-small"
                      onChange={(event) =>
                        setDraft((value) => ({
                          ...value,
                          courseId: event.target.value,
                          groupId: '',
                        }))
                      }
                      value={courseId}
                    >
                      {courses.map((course) => (
                        <option key={course.courseId} value={course.courseId}>
                          {course.courseName}
                        </option>
                      ))}
                    </select>
                  </Label>
                  <Label className="grid gap-1">
                    <Trans>Группа</Trans>
                    <select
                      className="min-h-10 rounded-md border border-input bg-surface px-3 text-small"
                      onChange={(event) =>
                        setDraft((value) => ({ ...value, groupId: event.target.value }))
                      }
                      value={draft.groupId}
                    >
                      <option value="">
                        <Trans>Все</Trans>
                      </option>
                      {groups.map((group) => (
                        <option key={group.groupId} value={group.groupId}>
                          {group.groupName}
                        </option>
                      ))}
                    </select>
                  </Label>
                  <Label className="grid gap-1">
                    <Trans>Показывать</Trans>
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
                      <option value="both">
                        <Trans>Всем</Trans>
                      </option>
                      <option value="student">
                        <Trans>Только школьнику</Trans>
                      </option>
                      <option value="family">
                        <Trans>Только родителям</Trans>
                      </option>
                    </select>
                  </Label>
                  <Label className="grid gap-1">
                    <Trans>Очность</Trans>
                    <select
                      className="min-h-10 rounded-md border border-input bg-surface px-3 text-small"
                      onChange={(event) =>
                        setDraft((value) => ({
                          ...value,
                          attendanceMode: event.target.value as CommunicationAttendanceMode,
                        }))
                      }
                      value={draft.attendanceMode}
                    >
                      <option value="all">
                        <Trans>Всем</Trans>
                      </option>
                      <option value="in_person">
                        <Trans>Только очные</Trans>
                      </option>
                      <option value="online">
                        <Trans>Только онлайн</Trans>
                      </option>
                    </select>
                  </Label>
                  <Label className="grid gap-1">
                    <Trans>Приоритет</Trans>
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
                <div className="grid gap-1">
                  <Label>
                    <Trans>Текст объявления (Markdown)</Trans>
                  </Label>
                  <Suspense
                    fallback={
                      <div className="min-h-[22rem] rounded-md border border-border p-3 text-caption text-muted-foreground">
                        <Trans>Загружаем редактор…</Trans>
                      </div>
                    }
                  >
                    <RichMarkdownEditor
                      onChange={(markdown) => setDraft((value) => ({ ...value, markdown }))}
                      onDocumentChange={setDocument}
                      onImageUpload={(image) => richMediaClient.uploadImage(image)}
                      onFileUpload={(file) => richMediaClient.uploadFile(file)}
                      value={draft.markdown}
                    />
                  </Suspense>
                </div>
                <div className="grid gap-3 sm:grid-cols-2">
                  <div className="grid gap-1">
                    <div className="flex items-center justify-between gap-2">
                      <Label>
                        <Trans>Начало показа · Москва</Trans>
                      </Label>
                      <Button
                        onClick={() =>
                          setDraft((value) => ({
                            ...value,
                            startsAt: moscowInput(new Date().toISOString()),
                          }))
                        }
                        size="sm"
                        type="button"
                        variant="outline"
                      >
                        <Trans>Сейчас</Trans>
                      </Button>
                    </div>
                    <Input
                      onChange={(event) =>
                        setDraft((value) => ({ ...value, startsAt: event.target.value }))
                      }
                      required
                      type="datetime-local"
                      value={draft.startsAt}
                    />
                  </div>
                  <Label className="grid gap-1">
                    <Trans>Конец показа · Москва</Trans>
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
                  <Trans>Разрешить получателю скрыть объявление</Trans>
                </Label>
                <p className="text-caption text-muted-foreground">
                  <Trans>
                    Скрытие действует только в текущем браузере получателя. Уже отправленный push
                    после изменения фильтров не отзывается и не повторяется. Внешние картинки
                    копируются на сервер.
                  </Trans>
                </p>
                <div className="flex flex-wrap gap-2">
                  <Button
                    disabled={mutation.isPending || courses.length === 0 || document === null}
                    type="submit"
                  >
                    {editing ? t`Сохранить изменения` : t`Запланировать`}
                  </Button>
                  {editing ? (
                    <Button
                      onClick={() => {
                        setEditing(null)
                        setDraft(emptyDraft)
                        setDocument(null)
                      }}
                      type="button"
                      variant="outline"
                    >
                      <Trans>Отмена</Trans>
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
              <AlertTitle>
                <Trans>Изменение не сохранено</Trans>
              </AlertTitle>
              <AlertDescription>{errorText(mutation.error)}</AlertDescription>
            </AlertContent>
          </Alert>
        ) : null}
      </PageSection>
      <PageSection title={t`Запланированные и прошлые`}>
        {banners.isPending ? <PageStatePanel state="loading" /> : null}
        {banners.error ? <PageStatePanel state="error" /> : null}
        {banners.data?.items.length === 0 ? <PageStatePanel state="empty" /> : null}
        <div className="space-y-3">
          {banners.data?.items.map((banner) => (
            <Card key={banner.bannerId}>
              <CardContent className="space-y-3 pt-4">
                <GroupBanner banner={banner} />
                <p className="text-caption text-muted-foreground">
                  {banner.audience === 'both'
                    ? t`Школьник и родитель`
                    : banner.audience === 'student'
                      ? t`Только школьник`
                      : t`Только родитель`}
                  {' · '}
                  {banner.attendanceMode === 'all'
                    ? t`Очно и онлайн`
                    : banner.attendanceMode === 'in_person'
                      ? t`Только очные`
                      : t`Только онлайн`}
                </p>
                <p className="font-num text-caption text-muted-foreground">
                  {dateTimeFormat(currentLocale(), {
                    dateStyle: 'short',
                    timeStyle: 'short',
                    timeZone: 'Europe/Moscow',
                  }).format(new Date(banner.startsAt))}{' '}
                  —{' '}
                  {dateTimeFormat(currentLocale(), {
                    dateStyle: 'short',
                    timeStyle: 'short',
                    timeZone: 'Europe/Moscow',
                  }).format(new Date(banner.endsAt))}
                </p>
                {banner.status === 'active' ? (
                  <div className="flex gap-2">
                    <Button onClick={() => beginEdit(banner)} size="sm" variant="outline">
                      <Trans>Изменить</Trans>
                    </Button>
                    <Button
                      onClick={() => mutation.mutate({ kind: 'cancel', banner })}
                      size="sm"
                      variant="ghost"
                    >
                      <Trans>Отменить</Trans>
                    </Button>
                  </div>
                ) : (
                  <p className="text-caption text-muted-foreground">
                    <Trans>Отменено</Trans>
                  </p>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      </PageSection>
    </PageLayout>
  )
}
