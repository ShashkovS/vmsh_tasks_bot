import { describe, expect, it } from 'vitest'

import { canonicalProductRoute } from './product-analytics'

describe('product analytics route canonicalization', () => {
  it('keeps a route shape but removes opaque IDs, query strings and hashes', () => {
    expect(canonicalProductRoute('/tasks/course.abc/group.def/5?answer=secret#solution')).toBe(
      '/tasks/:id/:id/:id',
    )
  })

  it('does not turn a URL into telemetry route data', () => {
    expect(canonicalProductRoute('/news')).toBe('/news')
    expect(canonicalProductRoute('/')).toBe('/')
  })
})
