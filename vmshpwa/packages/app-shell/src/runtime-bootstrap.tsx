import { LoaderCircle, TriangleAlert } from 'lucide-react'
import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'

import {
  ApiResponseError,
  fetchRuntime,
  type Audience,
  type FetchRuntimeOptions,
  type RuntimeConfig,
} from '@vmsh/contracts'
import { Button, Card, CardContent } from '@vmsh/ui'

const RuntimeConfigContext = createContext<RuntimeConfig | null>(null)
export const DEFAULT_RUNTIME_BOOTSTRAP_TIMEOUT_MS = 10_000

export interface RuntimeBootstrapProps {
  audience: Audience
  children: (runtime: RuntimeConfig) => ReactNode
  fetchImplementation?: FetchRuntimeOptions['fetchImplementation']
  timeoutMilliseconds?: number
}

type RuntimeBootstrapState =
  | { status: 'loading' }
  | { status: 'ready'; runtime: RuntimeConfig }
  | { status: 'error'; requestId?: string }

/**
 * This boundary is intentionally outside every router: Phase 0 requires a
 * validated audience/runtime tuple before any protected shell can render.
 * See `dev/development-plan/04-phase-0-baseline.md` and `docs/runtime-isolation.md`.
 */
export function RuntimeBootstrap({
  audience,
  children,
  fetchImplementation,
  timeoutMilliseconds = DEFAULT_RUNTIME_BOOTSTRAP_TIMEOUT_MS,
}: RuntimeBootstrapProps) {
  const [attempt, setAttempt] = useState(0)

  return (
    <RuntimeBootstrapRequest
      audience={audience}
      fetchImplementation={fetchImplementation}
      key={`${audience}:${attempt}`}
      onRetry={() => setAttempt((currentAttempt) => currentAttempt + 1)}
      timeoutMilliseconds={timeoutMilliseconds}
    >
      {children}
    </RuntimeBootstrapRequest>
  )
}

function RuntimeBootstrapRequest({
  audience,
  children,
  fetchImplementation,
  onRetry,
  timeoutMilliseconds,
}: RuntimeBootstrapProps & { onRetry: () => void }) {
  const [state, setState] = useState<RuntimeBootstrapState>({ status: 'loading' })

  useEffect(() => {
    const abortController = new AbortController()
    let active = true
    const timeout = window.setTimeout(() => abortController.abort(), timeoutMilliseconds)

    void fetchRuntime(audience, {
      ...(fetchImplementation ? { fetchImplementation } : {}),
      signal: abortController.signal,
    }).then(
      (runtime) => {
        window.clearTimeout(timeout)
        if (active) setState({ status: 'ready', runtime })
      },
      (error: unknown) => {
        window.clearTimeout(timeout)
        if (!active) return
        setState({
          status: 'error',
          ...(error instanceof ApiResponseError ? { requestId: error.requestId } : {}),
        })
      },
    )

    return () => {
      active = false
      window.clearTimeout(timeout)
      abortController.abort()
    }
  }, [audience, fetchImplementation, timeoutMilliseconds])

  if (state.status === 'loading') {
    return (
      <AppStartupScreen
        description="Подключаем личный кабинет к серверу ВМШ 179."
        state="loading"
        title="Проверяем подключение"
      />
    )
  }

  if (state.status === 'error') {
    return (
      <AppStartupScreen
        description="Сервер не подтвердил настройки этого раздела. Проверьте подключение и повторите попытку."
        onRetry={onRetry}
        state="error"
        title="Не удалось безопасно открыть кабинет"
        {...(state.requestId ? { requestId: state.requestId } : {})}
      />
    )
  }

  return (
    <RuntimeConfigContext value={state.runtime}>{children(state.runtime)}</RuntimeConfigContext>
  )
}

export function useRuntimeConfig(): RuntimeConfig {
  const runtime = useContext(RuntimeConfigContext)
  if (!runtime) throw new Error('useRuntimeConfig must be used inside RuntimeBootstrap')
  return runtime
}

export type AppStartupScreenProps =
  | {
      state: 'loading'
      title: string
      description: string
    }
  | {
      state: 'error'
      title: string
      description: string
      onRetry: () => void
      requestId?: string
    }

export function AppStartupScreen(props: AppStartupScreenProps) {
  const isError = props.state === 'error'
  return (
    <main className="grid min-h-svh place-items-center bg-background p-4 text-foreground">
      <Card className="w-full max-w-md">
        <CardContent
          aria-live={isError ? 'assertive' : 'polite'}
          className="flex items-start gap-3 pt-6"
          role={isError ? 'alert' : 'status'}
        >
          {isError ? (
            <TriangleAlert
              aria-hidden="true"
              className="mt-0.5 size-5 shrink-0 text-status-danger"
            />
          ) : (
            <LoaderCircle
              aria-hidden="true"
              className="mt-0.5 size-5 shrink-0 motion-safe:animate-spin"
            />
          )}
          <div className="min-w-0">
            <h1 className="font-medium">{props.title}</h1>
            <p className="mt-1 text-sm leading-6 text-muted-foreground">{props.description}</p>
            {isError && props.requestId ? (
              <p className="mt-2 break-all text-xs text-muted-foreground">
                Код обращения: {props.requestId}
              </p>
            ) : null}
            {isError ? (
              <Button className="mt-4" onClick={props.onRetry} size="sm" type="button">
                Повторить
              </Button>
            ) : null}
          </div>
        </CardContent>
      </Card>
    </main>
  )
}
