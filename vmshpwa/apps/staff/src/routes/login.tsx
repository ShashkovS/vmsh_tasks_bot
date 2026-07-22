import { createFileRoute } from '@tanstack/react-router'

import { StaffLoginPage } from '../pages'

export const Route = createFileRoute('/login')({ component: StaffLoginPage })
