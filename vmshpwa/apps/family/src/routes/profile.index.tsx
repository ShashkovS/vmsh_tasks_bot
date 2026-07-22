import { createFileRoute } from '@tanstack/react-router'

import { FamilyProfilePage } from '../pages'

export const Route = createFileRoute('/profile/')({ component: FamilyProfilePage })
