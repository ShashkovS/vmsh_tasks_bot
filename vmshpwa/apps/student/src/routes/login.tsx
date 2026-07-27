import { createFileRoute, useRouter } from '@tanstack/react-router'
import { useCallback } from 'react'
import { z } from 'zod'

import {
  AppStartupScreen,
  createAuthReturnHref,
  sanitizeAuthReturnTo,
  useAuthenticationLogin,
} from '@vmsh/app-shell'
import { studentLoginRequestSchema } from '@vmsh/contracts'

import { StudentLoginPage } from '../pages'

const searchSchema = z.object({
  returnTo: z.unknown().optional().transform(sanitizeAuthReturnTo),
})

export const Route = createFileRoute('/login')({
  validateSearch: searchSchema,
  component: StudentLoginRoute,
})

function StudentLoginRoute() {
  const { returnTo } = Route.useSearch()
  const router = useRouter()
  const returnHref = createAuthReturnHref('student', returnTo)
  const finishLogin = useCallback(() => {
    void router.navigate({
      href: returnHref,
      reloadDocument: true,
      replace: true,
    })
  }, [returnHref, router])
  const login = useAuthenticationLogin(finishLogin)

  if (login.isResolvingSession) {
    return (
      <AppStartupScreen
        description="Проверяем, выполнен ли вход на этом устройстве."
        state="loading"
        title="Проверяем вход"
      />
    )
  }

  return (
    <StudentLoginPage
      loginState={login.loginState}
      onSubmit={async (request) => {
        await login.submit(studentLoginRequestSchema.parse(request))
      }}
    />
  )
}
