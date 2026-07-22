import { createFileRoute } from '@tanstack/react-router'

import { StudentNewsPage } from '../pages'

export const Route = createFileRoute('/news/')({ component: StudentNewsPage })
