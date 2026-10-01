import { t } from '@lingui/core/macro'
import type { ServiceAvailability } from '@vmsh/contracts'

/** Pre-brand recovery screen; docs/branding.md and docs/smooth-redeploy.md.
 * Plain DOM keeps a single React root, mounted only after validated identity.
 */
export function renderBrandingWaiting(root: HTMLElement, state: ServiceAvailability): void {
  const main = document.createElement('main')
  main.className = 'grid min-h-svh place-items-center bg-background p-4 text-foreground'
  const card = document.createElement('div')
  card.className =
    'w-full max-w-md rounded-xl bg-card p-6 text-sm text-card-foreground ring-1 ring-foreground/10'
  card.setAttribute('role', 'status')
  card.setAttribute('aria-live', 'polite')
  const title = document.createElement('h1')
  title.className = 'font-medium'
  title.textContent =
    state.state === 'updating' ? t`Обновляем сервис` : t`Восстанавливаем соединение`
  const description = document.createElement('p')
  description.className = 'mt-1 leading-6 text-muted-foreground'
  description.textContent = state.prolonged
    ? state.state === 'updating'
      ? t`Обновление занимает больше времени. Мы продолжаем подключаться.`
      : t`Подключение занимает больше времени. Мы продолжаем пробовать.`
    : t`Кабинет продолжит работу автоматически после подключения.`
  card.append(title, description)
  main.append(card)
  root.replaceChildren(main)
}
