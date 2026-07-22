import { createFileRoute } from '@tanstack/react-router'

import { FamilyLoginPage } from '../pages'

export const Route = createFileRoute('/login')({ component: FamilyLoginPage })
