import { createFileRoute } from '@tanstack/react-router'
import { StaffTestingPage } from '../staff-testing-page'
export const Route = createFileRoute('/testing')({ component: StaffTestingPage })
