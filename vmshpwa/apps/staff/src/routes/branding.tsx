import { createFileRoute } from '@tanstack/react-router'
import { BrandingPage } from '../branding-page'

export const Route = createFileRoute('/branding')({ component: BrandingPage })
