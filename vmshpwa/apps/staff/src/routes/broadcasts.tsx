import { createFileRoute } from '@tanstack/react-router'

import { StaffGroupBannersPage } from '../staff-group-banners-page'

export const Route = createFileRoute('/broadcasts')({ component: StaffGroupBannersPage })
