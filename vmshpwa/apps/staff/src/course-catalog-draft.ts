export function clearCatalogDraft(key: string) {
  try {
    globalThis.localStorage.removeItem(key)
  } catch {
    // A denied cleanup does not turn a successful server write into an error.
  }
}
