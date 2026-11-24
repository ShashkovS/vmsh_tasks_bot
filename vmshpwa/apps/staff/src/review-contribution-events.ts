/** Confirmed saves only; docs/review-contribution.md. */
export function notifyContributionSaved() {
  window.dispatchEvent(new Event('review-contribution-saved'))
}
