import { createFileRoute } from '@tanstack/react-router'

import { StaffLessonsPage } from '../pages'

export const Route = createFileRoute('/lessons/')({ component: StaffLessonsPage })
