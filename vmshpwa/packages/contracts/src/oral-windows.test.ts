import { describe, expect, it } from 'vitest'

import { oralWindowJoinResponseSchema, studentOralWindowListResponseSchema } from './oral-windows'

describe('oral-window contracts', () => {
  it('keeps connection secrets out of the Student list', () => {
    const result = studentOralWindowListResponseSchema.parse({
      schemaVersion: 1,
      items: [
        {
          windowId: 'oral-window.1',
          sequenceNumber: 1,
          opensAt: '2026-10-05T11:00:00.000000Z',
          closesAt: '2026-10-05T13:00:00.000000Z',
          joinLabel: 'Подключиться к Zoom',
          state: 'open',
          joinAvailable: true,
          version: 1,
          joinUrl: 'https://must-be-stripped.example.test',
        },
      ],
      requestId: 'request.1',
    })

    expect(result.items[0]).not.toHaveProperty('joinUrl')
  })

  it('accepts the separately revealed HTTPS join details', () => {
    expect(
      oralWindowJoinResponseSchema.parse({
        schemaVersion: 1,
        join: {
          windowId: 'oral-window.1',
          joinLabel: 'Подключиться к Zoom',
          joinUrl: 'https://zoom.example.test/j/179',
          joinCode: '179179',
          closesAt: '2026-10-05T13:00:00.000000Z',
        },
        requestId: 'request.2',
      }).join.joinCode,
    ).toBe('179179')
  })
})
