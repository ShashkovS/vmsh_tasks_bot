import { createFileRoute } from '@tanstack/react-router'

import { OrganizerLink } from '@vmsh/app-shell'

import { FamilyProfilePage } from '../pages'

export const Route = createFileRoute('/profile/')({
  component: () => <FamilyProfilePage organizerLink={<OrganizerLink />} />,
})
