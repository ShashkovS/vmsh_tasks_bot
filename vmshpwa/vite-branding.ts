import { readdirSync, readFileSync } from 'node:fs'
import { join, sep } from 'node:path'
import type { Plugin } from 'vite'

/** Ship every reviewed identity, including offline icons; see docs/branding.md. */
export function brandingAssets(): Plugin {
  // Keep config imports testable: Vite transforms new URL assets in jsdom.
  // See packages/test-utils/src/vite-content-assets-proxy.test.ts.
  const root = join(import.meta.dirname, 'brands') + sep
  const files = readdirSync(root, { recursive: true, withFileTypes: true })
    .filter((entry) => entry.isFile())
    .map((entry) => ({
      path: `${entry.parentPath}/${entry.name}`,
      name: `brands/${entry.parentPath.slice(root.length)}/${entry.name}`.replaceAll('//', '/'),
    }))
  return {
    name: 'repository-branding',
    generateBundle() {
      for (const file of files)
        this.emitFile({ type: 'asset', fileName: file.name, source: readFileSync(file.path) })
    },
    configureServer(server) {
      server.middlewares.use((request, response, next) => {
        const pathname = (request.url ?? '').split('?')[0] ?? ''
        const file = files.find((candidate) => pathname.endsWith(`/${candidate.name}`))
        if (!file) return next()
        response.setHeader(
          'Content-Type',
          file.name.endsWith('.svg') ? 'image/svg+xml' : 'image/png',
        )
        response.end(readFileSync(file.path))
      })
    },
  }
}
