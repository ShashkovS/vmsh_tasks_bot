import { createFileRoute } from '@tanstack/react-router'

import { StaffReviewReactionInboxPage } from '../review-reaction-inbox-page'

export const Route = createFileRoute('/reactions')({ component: StaffReviewReactionInboxPage })
