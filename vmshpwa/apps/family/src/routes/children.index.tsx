import { createFileRoute } from '@tanstack/react-router'

import { FamilyChildrenPage } from '../family-children-page'

export const Route = createFileRoute('/children/')({ component: FamilyChildrenPage })
