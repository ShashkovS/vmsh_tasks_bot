import { createFileRoute } from '@tanstack/react-router'

import { FamilyNewsPage } from '../pages'

export const Route = createFileRoute('/news/')({ component: FamilyNewsPage })
