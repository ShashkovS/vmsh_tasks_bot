import { createFileRoute, lazyRouteComponent } from '@tanstack/react-router'

// Staff-only assistant connection settings; docs/ai-review-assistant.md.
export const Route = createFileRoute('/mcp-access')({
  component: lazyRouteComponent(() => import('../mcp-access-page'), 'McpAccessPage'),
})
