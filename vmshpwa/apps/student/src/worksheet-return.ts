import { useEffect } from 'react'

// docs/task-interaction-polish.md: retain the loaded archive and an exact task
// offset while the detail route mounts/unmounts; no answer content is stored.
export const worksheetPageSizes = new Map<string, number>()
export const worksheetExpandedProblems = new Map<string, Set<string>>()
let returnPosition: { url: string; taskId: string; top: number; historyIndex: unknown } | undefined

function historyIndex(): unknown {
  const state: unknown = window.history.state
  return typeof state === 'object' && state !== null && '__TSR_index' in state
    ? state.__TSR_index
    : undefined
}

export function rememberWorksheet(taskId: string) {
  const anchor = document.querySelector<HTMLElement>(
    `[data-task-return-id="${CSS.escape(taskId)}"]`,
  )
  if (!anchor) return
  returnPosition = {
    url: window.location.pathname + window.location.search,
    taskId,
    historyIndex: historyIndex(),
    top: anchor.getBoundingClientRect().top,
  }
}

export function backToWorksheet(): boolean {
  if (
    !returnPosition ||
    typeof returnPosition.historyIndex !== 'number' ||
    historyIndex() !== returnPosition.historyIndex + 1
  )
    return false
  window.history.back()
  return true
}

export function useWorksheetReturn(enabled = true) {
  useEffect(() => {
    if (!enabled) return
    const position = returnPosition
    if (!position || position.url !== window.location.pathname + window.location.search) return
    let frame = 0
    const restore = () => {
      cancelAnimationFrame(frame)
      frame = requestAnimationFrame(() => {
        const anchor = document.querySelector<HTMLElement>(
          `[data-task-return-id="${CSS.escape(position.taskId)}"]`,
        )
        if (anchor)
          window.scrollBy({
            top: anchor.getBoundingClientRect().top - position.top,
            behavior: 'instant',
          })
      })
    }
    const observer = new MutationObserver(restore)
    const sizes = new ResizeObserver(restore)
    observer.observe(document.body, { childList: true, subtree: true })
    sizes.observe(document.body)
    const stop = () => {
      observer.disconnect()
      sizes.disconnect()
      cancelAnimationFrame(frame)
      returnPosition = undefined
    }
    const timer = window.setTimeout(stop, 5_000)
    const events = ['wheel', 'touchstart', 'keydown', 'pointerdown'] as const
    for (const event of events) window.addEventListener(event, stop, { passive: true })
    restore()
    return () => {
      observer.disconnect()
      sizes.disconnect()
      cancelAnimationFrame(frame)
      window.clearTimeout(timer)
      for (const event of events) window.removeEventListener(event, stop)
    }
  }, [enabled])
}
