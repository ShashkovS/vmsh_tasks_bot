interface ImportMetaEnv {
  readonly VITE_ENABLE_MSW: string | undefined
  readonly VITE_PUBLIC_MEDIA_ORIGIN: string | undefined
  readonly VITE_SENTRY_DSN: string | undefined
  readonly VITE_SENTRY_RELEASE: string | undefined
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}

/** `.po` catalogs compiled at build time by `@lingui/vite-plugin` (see `vite-i18n.ts`). */
declare module '*.po' {
  import type { Messages } from '@lingui/core'
  export const messages: Messages
}
