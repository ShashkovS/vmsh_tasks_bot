import { createFileRoute } from '@tanstack/react-router'

import { StudentHomePage } from '../student-home-page'

export const Route = createFileRoute('/')({ component: StudentHomePage })
