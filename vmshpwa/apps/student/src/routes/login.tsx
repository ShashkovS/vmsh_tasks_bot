import { createFileRoute } from '@tanstack/react-router'

import { StudentLoginPage } from '../pages'

export const Route = createFileRoute('/login')({ component: StudentLoginPage })
