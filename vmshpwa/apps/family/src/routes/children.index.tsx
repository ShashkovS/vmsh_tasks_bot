import { createFileRoute } from '@tanstack/react-router'

import { FamilyChildrenPage } from '../pages'

export const Route = createFileRoute('/children/')({ component: FamilyChildrenPage })
