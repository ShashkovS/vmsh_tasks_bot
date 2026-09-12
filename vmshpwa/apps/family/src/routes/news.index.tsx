import { createFileRoute } from '@tanstack/react-router'

import { FamilyNewsFeedPage } from '../family-news-page'

export const Route = createFileRoute('/news/')({ component: FamilyNewsFeedPage })
