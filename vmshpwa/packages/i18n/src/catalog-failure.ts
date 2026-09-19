/**
 * Static last-resort screen for a failed Russian catalog. Without a catalog
 * React cannot render any product text, so this screen is plain DOM with a
 * fixed bilingual message. It only uses design-system utility classes.
 */
export function renderCatalogFailure(root: HTMLElement): void {
  const main = document.createElement('main')
  main.className = 'grid min-h-svh place-items-center bg-background p-4 text-foreground'
  const card = document.createElement('div')
  card.className =
    'w-full max-w-md rounded-xl bg-card p-6 text-sm text-card-foreground ring-1 ring-foreground/10'
  card.setAttribute('role', 'alert')

  const title = document.createElement('h1')
  title.className = 'font-medium'
  // eslint-disable-next-line lingui/no-unlocalized-strings -- bilingual copy shown when no catalog could load
  title.textContent = 'Не удалось загрузить интерфейс · Could not load the interface'
  const description = document.createElement('p')
  description.className = 'mt-1 leading-6 text-muted-foreground'
  description.textContent =
    // eslint-disable-next-line lingui/no-unlocalized-strings -- bilingual copy shown when no catalog could load
    'Проверьте подключение и обновите страницу. · Check the connection and reload the page.'
  const reload = document.createElement('button')
  reload.type = 'button'
  reload.className = 'mt-4 h-8 rounded-lg bg-primary px-3 text-primary-foreground'
  // eslint-disable-next-line lingui/no-unlocalized-strings -- bilingual copy shown when no catalog could load
  reload.textContent = 'Обновить · Reload'
  reload.addEventListener('click', () => window.location.reload())

  card.append(title, description, reload)
  main.append(card)
  root.replaceChildren(main)
}
