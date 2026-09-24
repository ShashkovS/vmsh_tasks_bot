import {
  expect,
  test as base,
  type BrowserContext,
  type Route,
  type WebSocketRoute,
} from '@playwright/test'

const gatewayHttpOrigin = 'http://127.0.0.1:5380'
const gatewayWebSocketOrigin = 'ws://127.0.0.1:5380'

/**
 * E2E browser traffic has one production-like origin and no external escape.
 *
 * The API process on 127.0.0.1:8380 is an upstream used by the loopback
 * gateway and Playwright's server readiness probe. Product pages must still
 * use the gateway origin, preserving the one-host cookie, Service Worker and
 * history boundaries from Phase 0.
 */
export function isAllowedE2eBrowserUrl(rawUrl: string): boolean {
  let url: URL
  try {
    url = new URL(rawUrl)
  } catch {
    return false
  }
  if (url.username !== '' || url.password !== '') return false
  return url.origin === gatewayHttpOrigin || url.origin === gatewayWebSocketOrigin
}

class NetworkGuard {
  readonly #expectedBlocked = new Map<string, number>()
  readonly #unexpectedBlocked: string[] = []

  expectBlocked(rawUrl: string): void {
    this.#expectedBlocked.set(rawUrl, (this.#expectedBlocked.get(rawUrl) ?? 0) + 1)
  }

  recordBlocked(rawUrl: string): void {
    const expectedCount = this.#expectedBlocked.get(rawUrl) ?? 0
    if (expectedCount === 1) {
      this.#expectedBlocked.delete(rawUrl)
      return
    }
    if (expectedCount > 1) {
      this.#expectedBlocked.set(rawUrl, expectedCount - 1)
      return
    }
    this.#unexpectedBlocked.push(rawUrl)
  }

  assertComplete(): void {
    const missingExpected = [...this.#expectedBlocked.entries()].flatMap(([rawUrl, count]) =>
      Array.from({ length: count }, () => rawUrl),
    )
    expect(
      this.#unexpectedBlocked,
      'The browser attempted network access outside the literal loopback E2E origin',
    ).toEqual([])
    expect(missingExpected, 'Expected network-guard probes were not observed').toEqual([])
  }
}

type E2eFixtures = {
  networkGuard: NetworkGuard
  networkIsolation: void
  secondaryContext: BrowserContext
}

async function installNetworkIsolation(
  context: BrowserContext,
  networkGuard: NetworkGuard,
): Promise<void> {
  await context.route('**/*', async (route: Route) => {
    const rawUrl = route.request().url()
    if (isAllowedE2eBrowserUrl(rawUrl)) {
      await route.continue()
      return
    }
    networkGuard.recordBlocked(rawUrl)
    await route.abort('blockedbyclient')
  })
  await context.routeWebSocket(/.*/, async (websocket: WebSocketRoute) => {
    const rawUrl = websocket.url()
    if (isAllowedE2eBrowserUrl(rawUrl)) {
      websocket.connectToServer()
      return
    }
    networkGuard.recordBlocked(rawUrl)
    await websocket.close({ code: 1008, reason: 'External network is disabled in E2E' })
  })
}

export const test = base.extend<E2eFixtures>({
  // Playwright validates fixture dependencies by requiring this object
  // destructuring shape even when the fixture has no dependencies.
  // eslint-disable-next-line no-empty-pattern
  networkGuard: async ({}, provide) => {
    const networkGuard = new NetworkGuard()
    await provide(networkGuard)
  },
  networkIsolation: [
    async ({ context, networkGuard }, use) => {
      await installNetworkIsolation(context, networkGuard)
      await use()
      networkGuard.assertComplete()
    },
    { auto: true },
  ],
  secondaryContext: async ({ browser, networkGuard }, provide) => {
    const context = await browser.newContext({ baseURL: gatewayHttpOrigin })
    await installNetworkIsolation(context, networkGuard)
    await provide(context)
    await context.close()
  },
})

export { expect }
export type { Page } from '@playwright/test'
