import { readFile } from 'node:fs/promises'
import { join, relative } from 'node:path'

import { formatter } from '@lingui/format-po'
import { lingui, linguiTransformerBabelPreset } from '@lingui/vite-plugin'
import babel from '@rolldown/plugin-babel'
import type { Plugin, PluginOption } from 'vite'

/**
 * Shared i18n build wiring for apps, Vitest and Storybook.
 * See `adr/0004-pwa-internationalization.md` and `docs/i18n.md`.
 *
 * - `lingui()` compiles imported `.po` catalogs at build time, so no ICU
 *   message is parsed in the browser.
 * - The Babel preset expands Lingui macros; its code filter sends only files
 *   importing `@lingui/*\/macro` through Babel. `@vitejs/plugin-react` v6 has
 *   no Babel of its own.
 */
export const linguiConfigPath = join(import.meta.dirname, 'lingui.config.ts')

const DEFAULT_CATALOG_MODULE = /\/src\/i18n\/catalog-ru\.ts$/

/**
 * Preloads the default-locale catalog chunk in parallel with the entry chunk,
 * so the pre-render catalog import adds no sequential request.
 */
function defaultCatalogPreload(): Plugin {
  let base = '/'
  return {
    name: 'vmsh:i18n-default-catalog-preload',
    apply: 'build',
    configResolved(config) {
      base = config.base
    },
    transformIndexHtml: {
      order: 'post',
      handler(_html, context) {
        const chunk = Object.values(context.bundle ?? {}).find(
          (output) =>
            output.type === 'chunk' &&
            output.facadeModuleId !== null &&
            DEFAULT_CATALOG_MODULE.test(output.facadeModuleId),
        )
        if (!chunk) return []
        return [
          {
            tag: 'link',
            attrs: { rel: 'modulepreload', crossorigin: true, href: `${base}${chunk.fileName}` },
            injectTo: 'head',
          },
        ]
      },
    },
  }
}

const MACRO_DESCRIPTOR_ID = /\/\*\* i18n \*\/\s*\{\s*id:\s*"([^"]+)"/g
const workspaceRoot = import.meta.dirname

/**
 * Production builds keep only message IDs in code (`descriptorFields: auto`),
 * so a message missing from the app's catalogs would render as a hash. This
 * guard fails the build instead: every ID produced by the macro must exist in
 * a `.po` catalog imported by the app (see `apps/<app>/src/i18n/`). It catches
 * a forgotten `make pwa-i18n-extract` and a package catalog not merged by the app.
 */
function catalogCoverageGuard(): Plugin {
  const usedIds = new Map<string, string>()
  const catalogFiles = new Set<string>()
  return {
    name: 'vmsh:i18n-catalog-coverage-guard',
    apply: 'build',
    enforce: 'pre',
    transform(code, id) {
      const path = id.split('?')[0] ?? id
      if (path.endsWith('.po')) {
        catalogFiles.add(path)
        return null
      }
      if (!code.includes('/** i18n */')) return null
      for (const match of code.matchAll(MACRO_DESCRIPTOR_ID)) {
        const messageId = match[1]
        if (messageId && !usedIds.has(messageId)) usedIds.set(messageId, path)
      }
      return null
    },
    async buildEnd(error) {
      if (error || usedIds.size === 0) return
      const poFormatter = formatter({ lineNumbers: false })
      const availableIds = new Set<string>()
      for (const file of catalogFiles) {
        const catalog = await poFormatter.parse(await readFile(file, 'utf8'), {
          locale: undefined,
          sourceLocale: 'ru',
          filename: file,
        })
        for (const messageId of Object.keys(catalog)) availableIds.add(messageId)
      }
      const missing = [...usedIds].filter(([messageId]) => !availableIds.has(messageId))
      if (missing.length === 0) return
      const origins = [...new Set(missing.map(([, path]) => relative(workspaceRoot, path)))]
      this.error(
        `${missing.length} Lingui message(s) are not in this app's catalogs. ` +
          `Run \`make pwa-i18n-extract\` and make sure the app merges every package catalog ` +
          `in src/i18n/catalog-<locale>.ts. Sources:\n  ${origins.sort().join('\n  ')}`,
      )
    },
  }
}

export function i18nPlugins(): PluginOption[] {
  return [
    lingui({ configPath: linguiConfigPath }),
    babel({
      presets: [linguiTransformerBabelPreset(undefined, { configPath: linguiConfigPath })],
    }),
    catalogCoverageGuard(),
    defaultCatalogPreload(),
  ]
}
