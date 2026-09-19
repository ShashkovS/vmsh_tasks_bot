import { createFileRoute } from '@tanstack/react-router'

import { StaffReviewQueuePage } from '../review-queue-page'

export const Route = createFileRoute('/review/')({ component: StaffReviewQueuePage })
