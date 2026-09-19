import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useMemo, useState, type FormEvent } from 'react'

import {
  PageStatePanel,
  createTelegramBindingClient,
  useAuthenticatedPrincipal,
  useAuthentication,
  useTelegramBindingOwnersQuery,
  useTelegramBindingsQuery,
} from '@vmsh/app-shell'
import {
  ApiResponseError,
  telegramBindingQueryKeys,
  type SaveTelegramBindingRequest,
  type TelegramBinding,
} from '@vmsh/contracts'
import { TelegramBindingsEditor, type CourseView } from '@vmsh/product'
import {
  Alert,
  AlertContent,
  AlertDescription,
  AlertTitle,
  Button,
  Card,
  CardContent,
  Input,
  Label,
} from '@vmsh/ui'

type Command =
  | { kind: 'create'; request: SaveTelegramBindingRequest }
  | { kind: 'verify' | 'disable' | 'restore'; binding: TelegramBinding }

function errorText(error: Error): string {
  if (error instanceof ApiResponseError) return error.message
  return 'Проверьте соединение и повторите попытку.'
}

export function StaffTelegramBindings() {
  const authentication = useAuthentication()
  const principal = useAuthenticatedPrincipal()
  if (principal.audience !== 'staff') throw new Error('Telegram bindings require Staff auth')
  const queryClient = useQueryClient()
  const client = useMemo(
    () =>
      createTelegramBindingClient(authentication.client.runtime, {
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
  const scope = { audience: 'staff' as const, accountId: principal.accountId }
  const owners = useTelegramBindingOwnersQuery(client, scope)
  const bindings = useTelegramBindingsQuery(client, scope)
  const [ownerKey, setOwnerKey] = useState('')
  const [purpose, setPurpose] = useState<'news_source' | 'materials_target'>('news_source')
  const [chatId, setChatId] = useState('')
  const [messageThreadId, setMessageThreadId] = useState('')
  const [titleCached, setTitleCached] = useState('')
  const mutation = useMutation({
    mutationFn: (command: Command) => {
      if (command.kind === 'create') return client.create(command.request)
      if (command.kind === 'verify')
        return client.verify(command.binding.publicId, command.binding.version)
      if (command.kind === 'disable')
        return client.disable(command.binding.publicId, command.binding.version)
      return client.restoreDraft(command.binding.publicId, command.binding.version)
    },
    onSuccess: async (_, command) => {
      if (command.kind === 'create') {
        setChatId('')
        setMessageThreadId('')
        setTitleCached('')
      }
      await queryClient.invalidateQueries({
        queryKey: telegramBindingQueryKeys.list(scope),
      })
    },
    onError: (error) => authentication.handleApiError(error),
  })

  if (owners.isPending || bindings.isPending) return <PageStatePanel state="loading" />
  if (owners.error || bindings.error) {
    const error = owners.error ?? bindings.error ?? new Error('Telegram bindings unavailable')
    return (
      <Alert role="alert" tone="danger">
        <AlertContent>
          <AlertTitle>Не удалось загрузить привязки Telegram</AlertTitle>
          <AlertDescription>{errorText(error)}</AlertDescription>
        </AlertContent>
      </Alert>
    )
  }

  const selectableOwners = owners.data.courses.flatMap((course) => [
    {
      key: `course:${course.courseId}`,
      ownerType: 'course' as const,
      ownerId: course.courseId,
      label: `${course.courseName} · курс`,
      disabled: course.status === 'archived',
    },
    ...course.groups.map((group) => ({
      key: `group:${group.groupId}`,
      ownerType: 'group' as const,
      ownerId: group.groupId,
      label: `${course.courseName} · ${group.groupName}`,
      disabled: group.status === 'archived',
    })),
  ])
  const selectedKey = ownerKey || selectableOwners.find((item) => !item.disabled)?.key || ''
  const selectedOwner = selectableOwners.find((item) => item.key === selectedKey)

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!selectedOwner || mutation.isPending) return
    const numericChatId = Number(chatId)
    const numericThreadId = messageThreadId ? Number(messageThreadId) : null
    mutation.mutate({
      kind: 'create',
      request: {
        schemaVersion: 1,
        ownerType: selectedOwner.ownerType,
        ownerId: selectedOwner.ownerId,
        purpose,
        chatId: numericChatId,
        messageThreadId: numericThreadId,
        titleCached: titleCached.trim() || null,
      },
    })
  }

  const byId = new Map(bindings.data.items.map((binding) => [binding.publicId, binding]))
  const run = (kind: 'verify' | 'disable' | 'restore', publicId: string) => {
    const binding = byId.get(publicId)
    if (binding && !mutation.isPending) mutation.mutate({ kind, binding })
  }
  const pendingBindingId =
    mutation.isPending && mutation.variables.kind !== 'create'
      ? mutation.variables.binding.publicId
      : null

  return (
    <div className="space-y-4">
      <Card>
        <CardContent className="pt-4">
          <form className="grid gap-3 lg:grid-cols-6 lg:items-end" onSubmit={submit}>
            <Label className="grid gap-1 lg:col-span-2">
              Курс или группа
              <select
                className="min-h-10 rounded-md border border-input bg-surface px-3 text-small"
                id="telegram-binding-owner"
                onChange={(event) => setOwnerKey(event.target.value)}
                value={selectedKey}
              >
                {selectableOwners.map((owner) => (
                  <option disabled={owner.disabled} key={owner.key} value={owner.key}>
                    {owner.label}
                  </option>
                ))}
              </select>
            </Label>
            <Label className="grid gap-1">
              Назначение
              <select
                className="min-h-10 rounded-md border border-input bg-surface px-3 text-small"
                onChange={(event) =>
                  setPurpose(event.target.value as 'news_source' | 'materials_target')
                }
                value={purpose}
              >
                <option value="news_source">Источник новостей</option>
                <option value="materials_target">Публикация материалов</option>
              </select>
            </Label>
            <Label className="grid gap-1">
              Chat ID
              <Input
                inputMode="numeric"
                onChange={(event) => setChatId(event.target.value)}
                placeholder="-100…"
                required
                value={chatId}
              />
            </Label>
            <Label className="grid gap-1">
              Topic ID
              <Input
                inputMode="numeric"
                onChange={(event) => setMessageThreadId(event.target.value)}
                placeholder="необязательно"
                value={messageThreadId}
              />
            </Label>
            <Label className="grid gap-1">
              Подпись
              <Input
                onChange={(event) => setTitleCached(event.target.value)}
                placeholder="необязательно"
                value={titleCached}
              />
            </Label>
            <Button disabled={!selectedOwner || mutation.isPending} type="submit">
              Сохранить черновик
            </Button>
          </form>
        </CardContent>
      </Card>

      {mutation.error ? (
        <Alert role="alert" tone="danger">
          <AlertContent>
            <AlertTitle>Изменение не сохранено</AlertTitle>
            <AlertDescription>{errorText(mutation.error)}</AlertDescription>
          </AlertContent>
        </Alert>
      ) : null}

      {owners.data.courses.map((course) => {
        const courseBindings = bindings.data.items.filter(
          (binding) => binding.courseId === course.courseId,
        )
        const courseView: CourseView = {
          id: course.courseId,
          code: course.courseId,
          name: course.courseName,
          subjectCode: course.courseName,
          accentIndex: 1,
        }
        return (
          <TelegramBindingsEditor
            bindings={courseBindings.map((binding) => ({
              id: binding.publicId,
              owner: binding.ownerType,
              ownerLabel: binding.ownerName,
              purpose: binding.purpose === 'news_source' ? 'news-source' : 'materials-target',
              chatLabel: binding.titleCached
                ? `${binding.titleCached} · ${binding.chatId}`
                : String(binding.chatId),
              ...(binding.messageThreadId === null
                ? {}
                : { topicLabel: `topic ${binding.messageThreadId}` }),
              status: binding.status,
            }))}
            course={courseView}
            key={course.courseId}
            onAdd={() => document.getElementById('telegram-binding-owner')?.focus()}
            onDisable={(publicId) => run('disable', publicId)}
            onRestore={(publicId) => run('restore', publicId)}
            onVerify={(publicId) => run('verify', publicId)}
            pendingBindingId={pendingBindingId}
          />
        )
      })}
    </div>
  )
}
