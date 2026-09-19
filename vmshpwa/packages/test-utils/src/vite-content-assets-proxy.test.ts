import { describe, expect, it } from 'vitest'

import familyConfig from '../../../apps/family/vite.config'
import staffConfig from '../../../apps/staff/vite.config'
import studentConfig from '../../../apps/student/vite.config'

const configEnvironment = {
  command: 'serve' as const,
  mode: 'test',
  isSsrBuild: false,
  isPreview: false,
}

describe('immutable content asset development proxy', () => {
  it('forwards the audience-neutral namespace in dev and preview for every app', () => {
    const configs = [
      studentConfig(configEnvironment),
      familyConfig(configEnvironment),
      staffConfig(configEnvironment),
    ]

    for (const config of configs) {
      expect(config.server?.proxy).toHaveProperty('/pwa-content-assets')
      expect(config.preview?.proxy).toHaveProperty('/pwa-content-assets')
    }
  })
})
