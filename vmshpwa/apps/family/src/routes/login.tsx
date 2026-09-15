import { createFileRoute, useRouter } from '@tanstack/react-router'
import { useCallback } from 'react'
import { z } from 'zod'

import {
  AppStartupScreen,
  createAuthReturnHref,
  sanitizeAuthReturnTo,
  useAuthenticationLogin,
} from '@vmsh/app-shell'
import { familyLoginRequestSchema } from '@vmsh/contracts'

import { FamilyLoginPage } from '../pages'

const searchSchema = z.object({
  returnTo: z.unknown().optional().transform(sanitizeAuthReturnTo),
})

export const Route = createFileRoute('/login')({
  validateSearch: searchSchema,
  component: FamilyLoginRoute,
})

function FamilyLoginRoute() {
  const { returnTo } = Route.useSearch()
  const router = useRouter()
  const returnHref = createAuthReturnHref('family', returnTo)
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
    <FamilyLoginPage
      loginState={login.loginState}
      onSubmit={async (request) => {
        await login.submit(familyLoginRequestSchema.parse(request))
      }}
    />
  )
}
