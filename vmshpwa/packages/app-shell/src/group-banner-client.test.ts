import { describe, expect, it, vi } from 'vitest'

import fixture from '@vmsh/contracts/fixtures/group-banners/list.v1.json'
import staffRuntimeFixture from '@vmsh/contracts/fixtures/runtime/staff.v1.json'
import studentRuntimeFixture from '@vmsh/contracts/fixtures/runtime/student.v1.json'
import { runtimeConfigSchemaForAudience } from '@vmsh/contracts'

import { createGroupBannerClient, createStaffGroupBannerClient } from './group-banner-client'

const runtime = runtimeConfigSchemaForAudience('student').parse(studentRuntimeFixture.response)

describe('group banner clients', () => {
  it('reads active audience banners', async () => {
    const fetchImplementation = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(fixture), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
    const client = createGroupBannerClient(runtime, 'student', { fetchImplementation })
    await expect(client.active()).resolves.toEqual(fixture)
    expect(fetchImplementation).toHaveBeenCalledWith(
      '/student/api/v1/banners/active',
      expect.objectContaining({ method: 'GET', credentials: 'include' }),
    )
  })

  it('sends optimistic Staff mutations', async () => {
    const item = fixture.items[0]!
    const fetchImplementation = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ schemaVersion: 1, item, requestId: 'test' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
    const staffRuntime = runtimeConfigSchemaForAudience('staff').parse(staffRuntimeFixture.response)
    const client = createStaffGroupBannerClient(staffRuntime, { fetchImplementation })
    await client.cancel(item.bannerId, item.version)
    expect(fetchImplementation).toHaveBeenCalledWith(
      `/staff/api/v1/group-banners/${item.bannerId}/cancel`,
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({ 'If-Match': `"${item.bannerId}:v1"` }),
      }),
    )
  })
})
