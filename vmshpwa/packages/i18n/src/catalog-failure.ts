/**
 * Static last-resort screen for a failed Russian catalog. Without a catalog
 * React cannot render any product text, so this screen is plain DOM with a
 * fixed bilingual message. See docs/service-failure-copy-20261004.md: a failed
 * bootstrap does not prove a user's internet outage.
 */
export function renderCatalogFailure(root: HTMLElement): void {
  const main = document.createElement('main')
  main.className = 'grid min-h-svh place-items-center bg-background p-4 text-foreground'
  const card = document.createElement('div')
  card.className =
    'w-full max-w-md rounded-xl bg-card p-6 text-sm text-card-foreground ring-1 ring-foreground/10'
  card.setAttribute('role', 'alert')

  // X0 (dev/ui-audit-20261104/BACKLOG.md): each language gets its own block instead of
  // «·»-glued halves; Russian first, English below in a quieter tone.
  const block = (heading: string, body: string, lang: string, quiet: boolean) => {
    const section = document.createElement('div')
    section.lang = lang
    section.className = quiet ? 'mt-4 border-t border-border pt-4 text-muted-foreground' : ''
    const title = document.createElement(quiet ? 'p' : 'h1')
    title.className = 'font-medium'
    title.textContent = heading
    const description = document.createElement('p')
    description.className = 'mt-1 leading-6 text-muted-foreground'
    description.textContent = body
    section.append(title, description)
    return section
  }
  const russian = block(
    // eslint-disable-next-line lingui/no-unlocalized-strings -- shown when no catalog could load
    'Не удалось загрузить интерфейс',
    // eslint-disable-next-line lingui/no-unlocalized-strings -- shown when no catalog could load
    'Попробуйте обновить страницу позже.',
    'ru',
    false,
  )
  const english = block(
    'Could not load the interface',
    'Please try reloading the page later.',
    'en',
    true,
  )
  const reload = document.createElement('button')
  reload.type = 'button'
  reload.className = 'mt-4 h-8 rounded-lg bg-primary px-3 text-primary-foreground'
  // eslint-disable-next-line lingui/no-unlocalized-strings -- shown when no catalog could load
  reload.textContent = 'Обновить · Reload'
  reload.addEventListener('click', () => window.location.reload())

  card.append(russian, english, reload)
  main.append(card)
  root.replaceChildren(main)
}
