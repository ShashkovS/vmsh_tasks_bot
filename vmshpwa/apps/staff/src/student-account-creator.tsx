import { t } from '@lingui/core/macro'
import { Trans } from '@lingui/react/macro'
import { useState, type FormEvent } from 'react'

import type { AdminStudentDirectoryEntry, CreateStudentAccountRequest } from '@vmsh/contracts'
import { Button, Input, Label } from '@vmsh/ui'

import {
  clearStudentAccountDraft,
  readStudentAccountDraft,
  studentAccountDraftKey,
  writeStudentAccountDraft,
} from './student-account-draft'

/** Minimal Phase-10 flow: the existing bot token stays server-side. */
export function StudentAccountCreator({
  pending,
  staffAccountId,
  storageNamespace,
  studentId,
  usernameSuggestion,
  onCreate,
}: {
  pending: boolean
  staffAccountId: string
  storageNamespace: string
  studentId: string
  usernameSuggestion: AdminStudentDirectoryEntry['usernameSuggestion']
  onCreate: (studentId: string, input: CreateStudentAccountRequest) => Promise<void>
}) {
  const draftKey = studentAccountDraftKey(storageNamespace, staffAccountId, studentId)
  const [draft, setDraft] = useState(() => {
    const stored = readStudentAccountDraft(globalThis.localStorage, draftKey)
    if (stored.username || usernameSuggestion?.state !== 'ready') return stored
    return { schemaVersion: 1 as const, username: usernameSuggestion.username ?? '' }
  })
  const [storageAvailable, setStorageAvailable] = useState(true)

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    await onCreate(studentId, draft)
    clearStudentAccountDraft(globalThis.localStorage, draftKey)
    setDraft({ schemaVersion: 1, username: '' })
  }

  return (
    <form
      className="grid gap-3 rounded-md border border-border p-3 sm:grid-cols-[minmax(12rem,20rem)_auto] sm:items-end"
      onSubmit={(event) => void submit(event).catch(() => undefined)}
    >
      <Label className="grid gap-1 text-small">
        <Trans>Логин школьника</Trans>
        <Input
          autoComplete="off"
          disabled={pending}
          maxLength={100}
          onChange={(event) => {
            const next = { schemaVersion: 1 as const, username: event.target.value }
            setDraft(next)
            setStorageAvailable(writeStudentAccountDraft(globalThis.localStorage, draftKey, next))
          }}
          required
          value={draft.username}
        />
      </Label>
      <Button disabled={pending} type="submit">
        {pending ? t`Создаём…` : t`Создать web-вход`}
      </Button>
      <p className="text-caption text-muted-foreground sm:col-span-2">
        <Trans>
          Паролем останется текущий Telegram-токен школьника. Он не передаётся в браузер.
        </Trans>
      </p>
      {usernameSuggestion?.state === 'ready' ? (
        <p className="text-caption text-muted-foreground sm:col-span-2">
          <Trans>Логин предложен по фамилии и дню рождения. Его можно исправить до создания.</Trans>
        </p>
      ) : usernameSuggestion?.state === 'collision' ? (
        <p className="text-small text-status-warning sm:col-span-2">
          <Trans>
            Предложенный логин {usernameSuggestion.username} уже занят или совпал у нескольких
            школьников. Введите уникальный логин вручную.
          </Trans>
        </p>
      ) : usernameSuggestion?.state === 'invalid_identity' ? (
        <p className="text-small text-status-warning sm:col-span-2">
          <Trans>
            Для предложения логина нужны корректные фамилия и дата рождения. Введите логин вручную.
          </Trans>
        </p>
      ) : null}
      {!storageAvailable ? (
        <p className="text-small text-status-error sm:col-span-2" role="alert">
          <Trans>Логин не сохраняется в этом браузере. Не закрывайте вкладку до отправки.</Trans>
        </p>
      ) : draft.username ? (
        <p className="text-caption text-muted-foreground sm:col-span-2" role="status">
          <Trans>Несохранённый логин хранится на этом устройстве.</Trans>
        </p>
      ) : null}
    </form>
  )
}
