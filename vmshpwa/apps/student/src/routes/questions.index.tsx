import { createFileRoute } from '@tanstack/react-router'

import { StudentSupportInboxPage } from '../student-support-pages'

export const Route = createFileRoute('/questions/')({ component: StudentSupportInboxPage })
