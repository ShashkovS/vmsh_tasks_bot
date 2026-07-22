import { createFileRoute } from '@tanstack/react-router'

import { BroadcastComposerPage } from '../pages'

export const Route = createFileRoute('/broadcasts')({ component: BroadcastComposerPage })
