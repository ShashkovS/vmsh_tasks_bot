import { createFileRoute, Outlet, Link, useRouterState } from '@tanstack/react-router'
import { MessageCircle, MessagesSquare } from 'lucide-react'
import { useAuthenticatedPrincipal, useOrganizerCount } from '@vmsh/app-shell'
import { cn } from '@vmsh/ui'

export const Route = createFileRoute('/questions')({ component: QuestionsLayout })

// docs/organizer-questions.md; dev/design-system/05-pages-and-flows.md: aligned section navigation.
function QuestionsLayout() {
  const principal = useAuthenticatedPrincipal()
  return (
    <>
      {principal.audience === 'staff' && principal.role === 'admin' ? (
        <QuestionSections accountId={principal.accountId} />
      ) : null}
      <Outlet />
    </>
  )
}

function QuestionSections({ accountId }: { accountId: string }) {
  const organizers = useRouterState({
    select: (state) => state.location.pathname.includes('/questions/organizers'),
  })
  const count = useOrganizerCount(accountId)
  const tabClass = (active: boolean) =>
    cn(
      'flex min-h-11 min-w-0 flex-auto items-center justify-center gap-1 rounded-md px-2 py-2 text-caption sm:gap-2 sm:text-small font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring sm:flex-none sm:px-4',
      active
        ? 'bg-primary text-primary-foreground'
        : 'text-muted-foreground hover:bg-surface-subtle hover:text-foreground',
    )
  return (
    <div className="mx-auto w-full max-w-[1500px] px-4 pt-5 sm:px-6 sm:pt-7">
      <nav
        aria-label="Разделы вопросов"
        className="flex gap-1 rounded-lg border border-border bg-surface p-1 sm:w-fit"
      >
        <Link
          to="/questions"
          search={{ state: 'awaiting_staff' }}
          activeOptions={{ exact: true }}
          aria-current={!organizers ? 'page' : undefined}
          className={tabClass(!organizers)}
        >
          <MessageCircle aria-hidden="true" className="hidden size-4 shrink-0 sm:block" />
          Школьников
        </Link>
        <Link
          to="/questions/organizers"
          search={{ state: 'awaiting_staff' }}
          aria-current={organizers ? 'page' : undefined}
          className={tabClass(organizers)}
        >
          <MessagesSquare aria-hidden="true" className="hidden size-4 shrink-0 sm:block" />
          Организаторам
          {count.data ? (
            <span
              aria-label={`Нужен ответ: ${count.data}`}
              className="rounded-full border border-current px-1.5 text-caption tabular-nums"
            >
              {count.data}
            </span>
          ) : null}
        </Link>
      </nav>
    </div>
  )
}
