import { createFileRoute, Link } from '@tanstack/react-router'
import { OrganizerLink, useAuthenticatedPrincipal } from '@vmsh/app-shell'
import { FamilyProfilePage } from '../pages'

function Profile() {
  const principal = useAuthenticatedPrincipal()
  if (principal.audience !== 'family') throw new Error('Family principal required')
  return (
    <FamilyProfilePage
      organizerLink={<OrganizerLink />}
      displayName={principal.displayName}
      childrenLinks={
        <ul className="space-y-2">
          {principal.linkedChildren.map((child) => (
            <li key={child.studentId}>
              <Link
                className="text-link underline"
                to="/children/$childId"
                params={{ childId: child.studentId }}
              >
                {child.displayName}
              </Link>
            </li>
          ))}
          {principal.linkedChildren.length === 0 ? <li>Нет связанных детей</li> : null}
        </ul>
      }
    />
  )
}
export const Route = createFileRoute('/profile/')({ component: Profile })
