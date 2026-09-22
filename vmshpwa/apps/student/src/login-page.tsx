import { t } from '@lingui/core/macro'
import { Trans } from '@lingui/react/macro'
import { Eye, EyeOff, Send, ShieldCheck } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { PageLayout } from '@vmsh/app-shell'
import type { StudentLoginRequest } from '@vmsh/contracts'
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

export type StudentLoginState =
  | 'idle'
  | 'pending'
  | 'invalid'
  | 'rate-limited'
  | 'account-unavailable'
  | 'blocked'
  | 'network'
  | 'error'

export function StudentLoginPage({
  initialUsername = '',
  loginState = 'idle',
  onSubmit,
}: {
  initialUsername?: string
  loginState?: StudentLoginState
  onSubmit?: (request: StudentLoginRequest) => void | Promise<void>
}) {
  const [showPassword, setShowPassword] = useState(false)
  const [username, setUsername] = useState(initialUsername)
  const [telegramToken, setTelegramToken] = useState('')
  const errorCopy = {
    invalid: t`Логин или токен не подошли. Проверьте раскладку и попробуйте ещё раз.`,
    'rate-limited': t`Слишком много попыток. Подождите немного и попробуйте ещё раз.`,
    'account-unavailable': t`Вход для этой учётной записи сейчас недоступен. Напишите администраторам.`,
    blocked: t`Доступ к аккаунту приостановлен. Напишите администраторам.`,
    network: t`Не удалось связаться с сервером. Проверьте интернет и попробуйте ещё раз.`,
    error: t`Не удалось безопасно завершить вход. Повторите попытку или напишите администраторам.`,
  } as const
  const pending = loginState === 'pending'
  const errorState = loginState === 'idle' || pending ? null : loginState

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (pending || !username.trim() || !telegramToken) return
    await onSubmit?.({ username, telegramToken })
  }

  return (
    <main className="grid min-h-svh place-items-center bg-background p-4">
      <PageLayout
        description={t`Используйте логин из письма после регистрации и текущий токен Telegram-бота как пароль.`}
        eyebrow={t`ВМШ 179`}
        title={t`Личный кабинет школьника`}
        width="reading"
      >
        <Card className="mx-auto max-w-md">
          <CardContent className="pt-5">
            <form className="space-y-4" onSubmit={handleSubmit}>
              {errorState ? (
                <Alert role="alert" tone="danger">
                  <ShieldCheck aria-hidden="true" />
                  <AlertContent>
                    <AlertTitle>
                      <Trans>Не удалось войти</Trans>
                    </AlertTitle>
                    <AlertDescription>{errorCopy[errorState]}</AlertDescription>
                  </AlertContent>
                </Alert>
              ) : null}
              <div className="space-y-1.5">
                <Label htmlFor="student-login">
                  <Trans>Логин</Trans>
                </Label>
                <Input
                  autoComplete="username"
                  disabled={pending}
                  id="student-login"
                  maxLength={128}
                  name="username"
                  onChange={(event) => setUsername(event.target.value)}
                  placeholder="petrov-14"
                  required
                  value={username}
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="student-password">
                  <Trans>Токен Telegram-бота</Trans>
                </Label>
                <div className="relative">
                  <Input
                    autoComplete="current-password"
                    className="pr-11"
                    disabled={pending}
                    id="student-password"
                    maxLength={512}
                    name="telegramToken"
                    onChange={(event) => setTelegramToken(event.target.value)}
                    required
                    type={showPassword ? 'text' : 'password'}
                    value={telegramToken}
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
                disabled={pending || !username.trim() || !telegramToken}
                type="submit"
              >
                <Send aria-hidden="true" /> {pending ? t`Входим…` : t`Войти`}
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
