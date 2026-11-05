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
    let stopped = false
    const restore = () => {
      if (stopped) return
      cancelAnimationFrame(frame)
      frame = requestAnimationFrame(() => {
        const anchor = document.querySelector<HTMLElement>(
          `[data-task-return-id="${CSS.escape(position.taskId)}"]`,
        )
        if (anchor) {
          const delta = anchor.getBoundingClientRect().top - position.top
          if (Math.abs(delta) >= 0.5) window.scrollBy({ top: delta, behavior: 'instant' })
        }
      })
    }
    const observer = new MutationObserver(restore)
    const sizes = new ResizeObserver(restore)
    observer.observe(document.body, { childList: true, subtree: true })
    sizes.observe(document.body)
    // Browser history can restore its own scroll after the first layout.
    // Keep the task offset until user input takes over (task-interaction-polish.md).
    window.addEventListener('scroll', restore, { passive: true })
    const stop = () => {
      stopped = true
      observer.disconnect()
      sizes.disconnect()
      cancelAnimationFrame(frame)
      window.removeEventListener('scroll', restore)
      returnPosition = undefined
    }
    const timer = window.setTimeout(stop, 5_000)
    const events = ['wheel', 'touchstart', 'keydown', 'pointerdown'] as const
    for (const event of events) window.addEventListener(event, stop, { passive: true })
    restore()
    return () => {
      stopped = true
      observer.disconnect()
      sizes.disconnect()
      cancelAnimationFrame(frame)
      window.clearTimeout(timer)
      window.removeEventListener('scroll', restore)
      for (const event of events) window.removeEventListener(event, stop)
    }
  }, [enabled])
}
