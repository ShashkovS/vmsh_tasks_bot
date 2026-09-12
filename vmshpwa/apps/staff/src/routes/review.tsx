import { createFileRoute, Outlet, Link, useRouterState } from '@tanstack/react-router'
import { useState, useEffect } from 'react'
import { useAuthentication, useAuthenticatedPrincipal } from '@vmsh/app-shell'
import { createBrowserStorageNamespace } from '@vmsh/contracts'
import { lastCompletedReview } from '../last-completed-review'
import { buttonVariants } from '@vmsh/ui'

export const Route = createFileRoute('/review')({ component: ReviewNavigation })
function ReviewNavigation() {
  const inHistory = useRouterState({
    select: (state) => state.location.pathname.includes('/review/history'),
  })
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
        aria-label="Проверки"
        className="mx-4 mb-3 flex flex-wrap items-center gap-2 border-b border-border py-3"
      >
        <Link
          className={buttonVariants({ variant: inHistory ? 'outline' : 'default', size: 'sm' })}
          aria-current={!inHistory ? 'page' : undefined}
          activeProps={{ 'aria-current': 'page' }}
          activeOptions={{ exact: true }}
          to="/review"
        >
          Очередь
        </Link>
        <Link
          className={buttonVariants({ variant: inHistory ? 'default' : 'outline', size: 'sm' })}
          activeProps={{ 'aria-current': 'page' }}
          to="/review/history"
        >
          Проверено
        </Link>
        {last && (
          <Link
            className={buttonVariants({ variant: 'ghost', size: 'sm' })}
            to="/review/history"
            search={{ review: last }}
          >
            Исправить последнюю
          </Link>
        )}
      </nav>
      <Outlet />
    </>
  )
}
