import { createFileRoute } from '@tanstack/react-router'

import { StudentProgressPage } from '../pages'

export const Route = createFileRoute('/progress')({ component: StudentProgressPage })
