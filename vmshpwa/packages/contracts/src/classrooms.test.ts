import { describe, expect, it } from 'vitest'

import fixture from '../fixtures/classrooms/catalog.v1.json'
import {
  classroomEtag,
  classroomListQuerySchema,
  classroomListResponseSchema,
  classroomQueryKeys,
  createClassroomRequestSchema,
} from './classrooms'

describe('classroom catalog contracts', () => {
  it('validates the committed catalog fixture', () => {
    const response = classroomListResponseSchema.parse(fixture)
    expect(response.items.map((room) => room.name)).toEqual(['201', 'Актовый зал'])
    expect(classroomEtag(response.items[0]!)).toBe('"classroom.201:v3"')
  })

  it('keeps server-side trimming possible while rejecting empty names', () => {
    expect(
      createClassroomRequestSchema.parse({ schemaVersion: 1, name: '  Актовый зал  ' }).name,
    ).toBe('  Актовый зал  ')
    expect(() => createClassroomRequestSchema.parse({ schemaVersion: 1, name: '   ' })).toThrow()
  })

  it('defaults list state and isolates query keys by filter and principal', () => {
    expect(classroomListQuerySchema.parse({})).toEqual({ search: '', status: 'active' })
    const admin = { audience: 'staff' as const, accountId: 'admin.one' }
    expect(classroomQueryKeys.list(admin)).not.toEqual(
      classroomQueryKeys.list(admin, { status: 'archived', search: 'зал' }),
    )
    expect(classroomQueryKeys.list(admin)).not.toEqual(
      classroomQueryKeys.list({ audience: 'staff', accountId: 'admin.two' }),
    )
  })

  it('rejects unknown response fields and invalid versions', () => {
    expect(() =>
      classroomListResponseSchema.parse({
        ...fixture,
        items: [{ ...fixture.items[0], version: 0 }],
      }),
    ).toThrow()
    expect(() => classroomListResponseSchema.parse({ ...fixture, unexpected: true })).toThrow()
  })
})
