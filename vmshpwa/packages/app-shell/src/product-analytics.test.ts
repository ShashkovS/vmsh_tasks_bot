import { describe, expect, it } from 'vitest'

import { canonicalProductRoute } from './product-analytics'

describe('product analytics route canonicalization', () => {
  it.each(['н', 'п', 'э', '%D0%BD', '%D0%BF', '%D1%8D'])(
    'normalizes group %s to the ASCII route contract',
    (group) => {
      expect(canonicalProductRoute(`/tasks/vmsh/${group}/0?task=5`)).toBe('/tasks/vmsh/:id/:id')
    },
  )
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
