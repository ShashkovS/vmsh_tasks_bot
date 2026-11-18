import { createFileRoute } from '@tanstack/react-router'

import { StudentNewsFeedPage } from '../student-news-page'

export const Route = createFileRoute('/news/')({ component: StudentNewsFeedPage })
