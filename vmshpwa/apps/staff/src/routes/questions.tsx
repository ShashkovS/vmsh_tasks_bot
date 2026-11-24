import { t } from '@lingui/core/macro'
import { Trans } from '@lingui/react/macro'
import { createFileRoute, Outlet, Link, useRouterState } from '@tanstack/react-router'
import { MessageCircle, MessagesSquare } from 'lucide-react'
import {
  sectionTabClassName,
  sectionTabsClassName,
  useAuthenticatedPrincipal,
  useOrganizerCount,
} from '@vmsh/app-shell'

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
  const tabClass = sectionTabClassName
  return (
    <div className="mx-auto w-full max-w-[1500px] px-4 pt-5 sm:px-6 sm:pt-7">
      <nav
        aria-label={t`Разделы вопросов`}
        className={sectionTabsClassName}
      >
        <Link
          to="/questions"
          search={{ state: 'awaiting_staff' }}
          activeOptions={{ exact: true }}
          aria-current={!organizers ? 'page' : undefined}
          className={tabClass(!organizers)}
        >
          <MessageCircle aria-hidden="true" className="size-4 shrink-0" />
          <Trans>Школьников</Trans>
        </Link>
        <Link
          to="/questions/organizers"
          search={{ state: 'awaiting_staff' }}
          aria-current={organizers ? 'page' : undefined}
          className={tabClass(organizers)}
        >
          <MessagesSquare aria-hidden="true" className="size-4 shrink-0" />
          <Trans>Организаторам</Trans>
          {count.data ? (
            <span
              aria-label={t`Нужен ответ: ${count.data}`}
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
