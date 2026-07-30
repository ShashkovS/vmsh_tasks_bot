import { useState, type FormEvent } from 'react'

import { type ManagedAccountStatus } from '@vmsh/contracts'
import { Button, Input, Label } from '@vmsh/ui'

export type AccountLifecycleCommand =
  | {
      kind: 'status'
      accountId: string
      version: number
      status: ManagedAccountStatus
    }
  | {
      kind: 'credential'
      accountId: string
      version: number
      credential: string
    }

interface AccountSummary {
  accountId: string
  credentialVersion: number
  status: ManagedAccountStatus
}

const statusLabels: Record<ManagedAccountStatus, string> = {
  active: 'Активен',
  blocked: 'Заблокирован',
  disabled: 'Отключён',
  archived: 'В архиве',
}

/** Existing-account controls from development Phase 10. */
export function StudentAccountControls({
  account,
  audience,
  pending,
  onChange,
}: {
  account: AccountSummary
  audience: 'student' | 'family'
  pending: boolean
  onChange: (command: AccountLifecycleCommand) => Promise<void>
}) {
  const [status, setStatus] = useState(account.status)
  const [credential, setCredential] = useState('')

  async function saveStatus(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    await onChange({
      kind: 'status',
      accountId: account.accountId,
      version: account.credentialVersion,
      status,
    })
  }

  async function saveCredential(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    await onChange({
      kind: 'credential',
      accountId: account.accountId,
      version: account.credentialVersion,
      credential,
    })
    setCredential('')
  }

  const title = audience === 'student' ? 'Аккаунт школьника' : 'Аккаунт семьи'
  const credentialLabel = audience === 'student' ? 'Новый Telegram-токен' : 'Новый пароль'

  return (
    <section className="grid gap-3 rounded-md border border-border p-3" aria-label={title}>
      <p className="text-small font-medium">{title}</p>
      <form className="flex flex-wrap items-end gap-2" onSubmit={(event) => void saveStatus(event)}>
        <Label className="grid min-w-44 gap-1 text-small">
          Состояние
          <select
            className="min-h-9 rounded-md border border-input bg-surface px-3 text-small"
            disabled={pending}
            onChange={(event) => setStatus(event.target.value as ManagedAccountStatus)}
            value={status}
          >
            {Object.entries(statusLabels).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </Label>
        <Button disabled={pending || status === account.status} size="sm" type="submit">
          Сохранить состояние
        </Button>
      </form>
      <form
        className="flex flex-wrap items-end gap-2"
        onSubmit={(event) => void saveCredential(event)}
      >
        <Label className="grid min-w-64 flex-1 gap-1 text-small">
          {credentialLabel}
          <Input
            autoComplete="new-password"
            disabled={pending}
            maxLength={256}
            minLength={audience === 'family' ? 8 : 1}
            onChange={(event) => setCredential(event.target.value)}
            required
            type="password"
            value={credential}
          />
        </Label>
        <Button
          disabled={pending || credential.length === 0}
          size="sm"
          type="submit"
          variant="outline"
        >
          Заменить данные для входа
        </Button>
      </form>
      <p className="text-caption text-muted-foreground">
        После изменения все текущие сессии этого аккаунта завершатся. Токен или пароль в браузере не
        сохраняется.
      </p>
    </section>
  )
}
