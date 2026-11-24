export function rememberCompletedReview(namespace: string, accountId: string, reviewId: string) {
  try {
    window.localStorage.setItem(`${namespace}:last-review:${accountId}`, reviewId)
  } catch {
    /* best effort pointer */
  }
  window.dispatchEvent(new Event('review-completed'))
}

export function lastCompletedReview(namespace: string, accountId: string): string | null {
  try {
    return window.localStorage.getItem(`${namespace}:last-review:${accountId}`)
  } catch {
    return null
  }
}
