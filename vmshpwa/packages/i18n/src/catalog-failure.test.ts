import { afterEach, describe, expect, it, vi } from 'vitest'

import { renderCatalogFailure } from './catalog-failure'

// Static bilingual screen for an unavailable Russian catalog (docs/i18n.md).
describe('renderCatalogFailure', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('replaces the root with a bilingual alert and a reload button', () => {
    const root = document.createElement('div')
    root.append(document.createElement('span'))
    const reload = vi.fn()
    vi.spyOn(window, 'location', 'get').mockReturnValue({ ...window.location, reload })

    renderCatalogFailure(root)

    const alert = root.querySelector('[role="alert"]')
    expect(alert?.textContent).toContain('Не удалось загрузить интерфейс')
    expect(alert?.textContent).toContain('Could not load the interface')
    root.querySelector('button')?.click()
    expect(reload).toHaveBeenCalledOnce()
    expect(root.querySelector('span')).toBeNull()
  })
})
