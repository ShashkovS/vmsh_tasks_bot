import { http, HttpResponse } from 'msw'

import { RUNTIME_CONTRACT_VERSION, type Audience, type RuntimeConfig } from '@vmsh/contracts'

export function runtimeFixture(audience: Audience, instance = 'storybook'): RuntimeConfig {
  const appBase = `/${audience === 'staff' ? 'staff' : audience}`
  return {
    contractVersion: RUNTIME_CONTRACT_VERSION,
    audience,
    appBase,
    apiBase: `${appBase}/api/v1`,
    websocketPath: `${appBase}/ws`,
    instance,
    serverTime: '2026-07-22T12:00:00Z',
    requestId: `fixture-${audience}`,
    features: { telegram: false, google: false, nats: false, prototype: true },
  }
}

export const runtimeHandlers = (audience: Audience) => [
  http.get(`/${audience}/api/v1/runtime`, () => HttpResponse.json(runtimeFixture(audience))),
]

export const prototypeLesson = {
  id: '2025-21-n',
  number: 21,
  level: 'Начинающие',
  opensAt: '2026-07-20T13:30:00Z',
  closesAt: '2026-07-26T10:00:00Z',
  tasks: [
    { id: '2025.21n.01', title: 'Разнообразные вагоны', type: 'test', status: 'correct' },
    { id: '2025.21n.06а', title: 'Расставьте 8 ладей', type: 'written', status: 'review' },
    { id: '2025.21n.08', title: 'Пример на вычитание', type: 'oral', status: 'unopened' },
  ],
} as const
