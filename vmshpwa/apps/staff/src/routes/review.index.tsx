import { createFileRoute } from '@tanstack/react-router'

import { ReviewQueuePage } from '../pages'

export const Route = createFileRoute('/review/')({ component: ReviewQueuePage })
