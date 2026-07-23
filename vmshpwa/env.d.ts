interface ImportMetaEnv {
  readonly VITE_ENABLE_MSW: string | undefined
  readonly VITE_PUBLIC_MEDIA_ORIGIN: string | undefined
  readonly VITE_SENTRY_DSN: string | undefined
  readonly VITE_SENTRY_RELEASE: string | undefined
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
