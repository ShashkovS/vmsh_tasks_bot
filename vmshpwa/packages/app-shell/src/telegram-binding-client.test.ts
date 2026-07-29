import fixture from '@vmsh/contracts/fixtures/telegram-bindings/list.v1.json'
import runtimeFixture from '@vmsh/contracts/fixtures/runtime/staff.v1.json'
import { runtimeConfigSchemaForAudience, telegramBindingListResponseSchema } from '@vmsh/contracts'
import { describe, expect, it, vi } from 'vitest'

import { createTelegramBindingClient } from './telegram-binding-client'

const runtime = runtimeConfigSchemaForAudience('staff').parse(runtimeFixture.response)
const parsedFixture = telegramBindingListResponseSchema.parse(fixture)
const binding = parsedFixture.items[0]!

describe('telegram binding client', () => {
  it('loads selectable owners from the Staff API', async () => {
    const fetchImplementation = vi.fn<typeof fetch>().mockResolvedValue(
      Response.json({
        schemaVersion: 1,
        courses: [
          {
            courseId: binding.courseId,
            courseName: binding.courseName,
            status: 'active',
            groups: [],
          },
        ],
        requestId: 'owners-request',
      }),
    )
    const owners = await createTelegramBindingClient(runtime, {
      fetchImplementation,
    }).owners()
    expect(owners.courses[0]?.courseId).toBe(binding.courseId)
    expect(fetchImplementation.mock.calls[0]?.[0]).toBe('/staff/api/v1/telegram-binding-owners')
  })

  it('uses the Staff API and validates the list', async () => {
    const fetchImplementation = vi.fn<typeof fetch>().mockResolvedValue(Response.json(fixture))
    const client = createTelegramBindingClient(runtime, { fetchImplementation })

    expect((await client.list({ courseId: binding.courseId })).items).toHaveLength(2)
    expect(fetchImplementation.mock.calls[0]?.[0]).toBe(
      `/staff/api/v1/telegram-bindings?courseId=${binding.courseId}`,
    )
  })

  it('sends a strict create request', async () => {
    const fetchImplementation = vi.fn<typeof fetch>().mockResolvedValue(
      Response.json({
        schemaVersion: 1,
        binding: { ...binding, status: 'draft', verifiedAt: null, version: 1 },
        requestId: 'create-binding',
      }),
    )
    const client = createTelegramBindingClient(runtime, { fetchImplementation })
    await client.create({
      schemaVersion: 1,
      ownerType: binding.ownerType,
      ownerId: binding.ownerId,
      purpose: binding.purpose,
      chatId: binding.chatId,
      messageThreadId: binding.messageThreadId,
      titleCached: binding.titleCached,
    })

    expect(fetchImplementation.mock.calls[0]?.[1]).toEqual(
      expect.objectContaining({ method: 'POST', credentials: 'include' }),
    )
  })

  it('uses exact ETags for edit and status changes', async () => {
    const response = {
      schemaVersion: 1,
      binding,
      requestId: 'binding-mutation',
    }
    const fetchImplementation = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(Response.json(response))
      .mockResolvedValueOnce(
        Response.json({
          ...response,
          binding: { ...binding, status: 'disabled', version: 3 },
        }),
      )
      .mockResolvedValueOnce(Response.json(response))
    const client = createTelegramBindingClient(runtime, { fetchImplementation })
    const request = {
      schemaVersion: 1 as const,
      ownerType: binding.ownerType,
      ownerId: binding.ownerId,
      purpose: binding.purpose,
      chatId: binding.chatId,
      messageThreadId: binding.messageThreadId,
      titleCached: binding.titleCached,
    }

    await client.update(binding.publicId, 2, request)
    await client.disable(binding.publicId, 2)
    await client.verify(binding.publicId, 2)

    expect(fetchImplementation.mock.calls[0]?.[1]?.headers).toEqual(
      expect.objectContaining({ 'If-Match': `"${binding.publicId}:v2"` }),
    )
    expect(fetchImplementation.mock.calls[1]?.[0]).toContain('/disable')
    expect(fetchImplementation.mock.calls[2]?.[0]).toContain('/verify')
  })

  it('rejects a malformed server response', async () => {
    const fetchImplementation = vi
      .fn<typeof fetch>()
      .mockResolvedValue(Response.json({ ...fixture, items: [{ ...binding, chatId: 0 }] }))
    await expect(
      createTelegramBindingClient(runtime, { fetchImplementation }).list(),
    ).rejects.toThrow()
  })
})
