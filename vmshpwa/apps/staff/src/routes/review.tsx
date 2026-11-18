import { t } from '@lingui/core/macro'
import { Trans } from '@lingui/react/macro'
import { createFileRoute, Outlet, Link, useRouterState } from '@tanstack/react-router'
import { useState, useEffect } from 'react'
import {
  sectionTabClassName,
  sectionTabsClassName,
  useAuthentication,
  useAuthenticatedPrincipal,
} from '@vmsh/app-shell'
import { createBrowserStorageNamespace } from '@vmsh/contracts'
import { reviewQueueSearchSchema } from '../review-queue-model'
import { lastCompletedReview } from '../last-completed-review'
import { buttonVariants } from '@vmsh/ui'

export const Route = createFileRoute('/review')({
  validateSearch: reviewQueueSearchSchema,
  component: ReviewNavigation,
})
function ReviewNavigation() {
  const pathname = useRouterState({
    select: (state) => state.location.pathname,
  })
  const inHistory = pathname.includes('/review/history')
  const inSheet = pathname.includes('/review/sheet')
  const auth = useAuthentication()
  const principal = useAuthenticatedPrincipal()
  const namespace = createBrowserStorageNamespace(auth.client.runtime)
  const [last, setLast] = useState(() => lastCompletedReview(namespace, principal.accountId))
  useEffect(() => {
    const update = () => setLast(lastCompletedReview(namespace, principal.accountId))
    update()
    window.addEventListener('review-completed', update)
    return () => window.removeEventListener('review-completed', update)
  }, [namespace, principal.accountId])
  return (
    <>
      <nav
        aria-label={t`Проверки`}
        className={`mx-4 mb-3 mt-3 ${sectionTabsClassName}`}
      >
        <Link
          className={sectionTabClassName(!inHistory && !inSheet)}
          aria-current={!inHistory && !inSheet ? 'page' : undefined}
          activeProps={{ 'aria-current': 'page' }}
          activeOptions={{ exact: true }}
          to="/review"
          search={true}
        >
          <Trans>Очередь</Trans>
        </Link>
        <Link
          className={sectionTabClassName(inHistory)}
          activeProps={{ 'aria-current': 'page' }}
          to="/review/history"
        >
          <Trans>Проверено</Trans>
        </Link>
        <Link
          className={sectionTabClassName(inSheet)}
          aria-current={inSheet ? 'page' : undefined}
          activeProps={{ 'aria-current': 'page' }}
          to="/review/sheet"
          search={{ mode: 'pending' }}
        >
          <Trans>Простыня</Trans>
        </Link>
        {last && (
          <Link
            className={`${buttonVariants({ variant: 'ghost', size: 'sm' })} mb-1 ml-auto`}
            to="/review/history"
            search={{ review: last }}
          >
            <Trans>Исправить последнюю</Trans>
          </Link>
        )}
      </nav>
      <Outlet />
    </>
  )
}
