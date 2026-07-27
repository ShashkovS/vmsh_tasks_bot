import { createMemoryHistory, createRouter } from '@tanstack/react-router'
import { describe, expect, it } from 'vitest'

import { createRouterAuthReturnTo } from '@vmsh/app-shell'

import { routeTree } from './routeTree.gen'

describe('Student authentication routing', () => {
  it('matches a trailing-slash login URL and defaults its validated returnTo', async () => {
    const router = createRouter({
      routeTree,
      basepath: '/student',
      history: createMemoryHistory({ initialEntries: ['/student/login/'] }),
    })

    await router.load()

    expect(router.state.matches.at(-1)?.routeId).toBe('/login')
    expect(router.state.matches.at(-1)?.search).toMatchObject({ returnTo: '/' })
  })

  it('keeps a safe intended route with search and one hash marker', async () => {
    const returnTo = '/tasks/41n-6?course=math#part-2'
    const router = createRouter({
      routeTree,
      basepath: '/student',
      history: createMemoryHistory({
        initialEntries: [`/student/login?returnTo=${encodeURIComponent(returnTo)}`],
      }),
    })

    await router.load()

    expect(router.state.matches.at(-1)?.search).toMatchObject({ returnTo })
  })

  it('turns the router location into one exact deep-link hash', async () => {
    const router = createRouter({
      routeTree,
      basepath: '/student',
      history: createMemoryHistory({
        initialEntries: ['/student/tasks?course=math#part-2'],
      }),
    })

    await router.load()

    expect(router.state.location.hash).toBe('part-2')
    expect(
      createRouterAuthReturnTo('student', {
        pathname: router.state.location.pathname,
        search: router.state.location.searchStr,
        hash: router.state.location.hash ? `#${router.state.location.hash}` : '',
      }),
    ).toBe('/tasks?course=math#part-2')
  })
})
