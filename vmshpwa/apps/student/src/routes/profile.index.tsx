import { createFileRoute } from '@tanstack/react-router'

import { StudentProfilePage } from '../student-profile-page'

export const Route = createFileRoute('/profile/')({ component: StudentProfilePage })
