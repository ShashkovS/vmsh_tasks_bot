import { t } from '@lingui/core/macro'
import { Trans } from '@lingui/react/macro'
import { Eye, EyeOff } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { PageLayout } from '@vmsh/app-shell'
import type { StaffLoginRequest } from '@vmsh/contracts'
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

export type StaffLoginState =
  'idle' | 'pending' | 'invalid' | 'rate-limited' | 'account-unavailable' | 'network' | 'error'

export function StaffLoginPage({
  invalid = false,
  loginState,
  onSubmit,
}: {
  invalid?: boolean
  loginState?: StaffLoginState
  onSubmit?: (request: StaffLoginRequest) => void | Promise<void>
}) {
  const [showPassword, setShowPassword] = useState(false)
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const effectiveState = loginState ?? (invalid ? 'invalid' : 'idle')
  const pending = effectiveState === 'pending'
  const errorCopy = {
    invalid: t`Логин или пароль не подошли. Проверьте раскладку и попробуйте ещё раз.`,
    'rate-limited': t`Слишком много попыток. Подождите немного и попробуйте ещё раз.`,
    'account-unavailable': t`Вход для этой учётной записи сейчас недоступен. Напишите администраторам.`,
    network: t`Не удалось связаться с сервером. Проверьте интернет и попробуйте ещё раз.`,
    error: t`Не удалось безопасно завершить вход. Повторите попытку или напишите администраторам.`,
  } as const
  const errorState = effectiveState === 'idle' || pending ? null : effectiveState

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (pending || !username.trim() || !password) return
    await onSubmit?.({ username, password })
  }

  return (
    <main className="grid min-h-svh place-items-center bg-background p-4">
      <PageLayout
        description={t`Учитель видит разрешённые группы; admin — административные разделы.`}
        eyebrow={t`ВМШ 179`}
        title={t`Вход для преподавателя`}
        width="reading"
      >
        <Card className="mx-auto max-w-md">
          <CardContent className="pt-5">
            <form className="space-y-4" onSubmit={handleSubmit}>
              {errorState ? (
                <Alert role="alert" tone="danger">
                  <AlertContent>
                    <AlertTitle>
                      <Trans>Не удалось войти</Trans>
                    </AlertTitle>
                    <AlertDescription>{errorCopy[errorState]}</AlertDescription>
                  </AlertContent>
                </Alert>
              ) : null}
              <div className="space-y-1.5">
                <Label htmlFor="staff-login">
                  <Trans>Логин</Trans>
                </Label>
                <Input
                  autoComplete="username"
                  disabled={pending}
                  id="staff-login"
                  maxLength={128}
                  name="username"
                  onChange={(event) => setUsername(event.target.value)}
                  required
                  value={username}
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="staff-password">
                  <Trans>Пароль</Trans>
                </Label>
                <div className="relative">
                  <Input
                    autoComplete="current-password"
                    className="pr-11"
                    disabled={pending}
                    id="staff-password"
                    maxLength={512}
                    name="password"
                    onChange={(event) => setPassword(event.target.value)}
                    required
                    type={showPassword ? 'text' : 'password'}
                    value={password}
                  />
                  <Button
                    aria-label={showPassword ? t`Скрыть пароль` : t`Показать пароль`}
                    className="absolute top-1/2 right-1 -translate-y-1/2"
                    disabled={pending}
                    onClick={() => setShowPassword((value) => !value)}
                    size="icon-sm"
                    type="button"
                    variant="ghost"
                  >
                    {showPassword ? <EyeOff aria-hidden="true" /> : <Eye aria-hidden="true" />}
                  </Button>
                </div>
              </div>
              <Button
                aria-busy={pending}
                className="w-full"
                disabled={pending || !username.trim() || !password}
                type="submit"
              >
                {pending ? t`Входим…` : t`Войти`}
              </Button>
              <p className="text-center text-caption text-muted-foreground">
                <Trans>
                  Не помните доступ? Напишите на{' '}
                  <a className="text-link underline" href="mailto:vmsh@179.ru">
                    vmsh@179.ru
                  </a>
                  .
                </Trans>
              </p>
            </form>
          </CardContent>
        </Card>
      </PageLayout>
    </main>
  )
}
