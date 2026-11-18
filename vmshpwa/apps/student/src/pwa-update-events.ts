export const safePwaUpdateEvent = 'vmsh:safe-pwa-update'

export function announceSafePwaUpdateMoment() {
  window.dispatchEvent(new Event(safePwaUpdateEvent))
}
