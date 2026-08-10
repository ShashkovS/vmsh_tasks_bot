import { createFileRoute } from '@tanstack/react-router'

import { StaffLessonsPage } from '../staff-lessons-page'

export const Route = createFileRoute('/lessons/')({ component: StaffLessonsPage })
