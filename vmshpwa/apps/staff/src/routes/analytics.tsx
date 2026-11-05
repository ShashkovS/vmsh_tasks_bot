import { createFileRoute } from '@tanstack/react-router'
import { ProductAnalyticsPage } from '../product-analytics-page'

export const Route = createFileRoute('/analytics')({ component: ProductAnalyticsPage })
