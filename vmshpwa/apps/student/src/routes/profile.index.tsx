import { createFileRoute } from '@tanstack/react-router'

import { StudentProfilePage } from '../pages'

export const Route = createFileRoute('/profile/')({ component: StudentProfilePage })
