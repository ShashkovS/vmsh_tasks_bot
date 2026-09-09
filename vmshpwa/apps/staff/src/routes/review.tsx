import { createFileRoute, Outlet, Link } from '@tanstack/react-router'
import { useState, useEffect } from 'react'
import { useAuthentication, useAuthenticatedPrincipal } from '@vmsh/app-shell'
import { createBrowserStorageNamespace } from '@vmsh/contracts'
import { lastCompletedReview } from '../last-completed-review'

export const Route = createFileRoute('/review')({ component: ReviewNavigation })
function ReviewNavigation() {
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
      <nav aria-label="Проверки" className="flex flex-wrap gap-4 py-3">
        <Link to="/review">Очередь</Link>
        <Link to="/review/history">Завершённые проверки</Link>
        {last && (
          <Link to="/review/history" search={{ review: last }}>
            Исправить последнюю свою проверку
          </Link>
        )}
      </nav>
      <Outlet />
    </>
  )
}
