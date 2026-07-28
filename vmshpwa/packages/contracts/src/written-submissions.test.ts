import { describe, expect, it } from 'vitest'

import fixture from '../fixtures/submissions/written-thread.v1.json'

import {
  createWrittenAttachmentResponseSchema,
  createWrittenEntryRequestSchema,
  submitWrittenEntryRequestSchema,
  writtenSubmissionFixtureSchema,
  writtenSubmissionQueryKeys,
  writtenAttachmentUploadMetadataSchema,
  writtenThreadResponseSchema,
} from './written-submissions'

describe('Phase-5 written-submission contracts', () => {
  it('keeps the fixture in parity with create, submit and history contracts', () => {
    expect(writtenSubmissionFixtureSchema.parse(fixture)).toEqual(fixture)
  })

  it('rejects client-controlled identity, non-UTC time and duplicate attachments', () => {
    expect(
      createWrittenEntryRequestSchema.safeParse({
        ...fixture.createRequest,
        studentId: 'user-client-controlled',
      }).success,
    ).toBe(false)
    expect(
      createWrittenEntryRequestSchema.safeParse({
        ...fixture.createRequest,
        clientCreatedAt: '2026-09-20T13:04:05+03:00',
      }).success,
    ).toBe(false)
    expect(
      submitWrittenEntryRequestSchema.safeParse({
        ...fixture.submitRequest,
        attachmentIds: ['attachment-one', 'attachment-one'],
      }).success,
    ).toBe(false)
  })

  it('validates bounded multipart metadata and the stored WebP response', () => {
    expect(writtenAttachmentUploadMetadataSchema.parse(fixture.attachmentMetadata)).toEqual(
      fixture.attachmentMetadata,
    )
    expect(createWrittenAttachmentResponseSchema.parse(fixture.attachmentResponse)).toEqual(
      fixture.attachmentResponse,
    )
    expect(
      writtenAttachmentUploadMetadataSchema.safeParse({
        ...fixture.attachmentMetadata,
        ordinal: 10,
      }).success,
    ).toBe(false)
  })

  it('rejects cross-problem and empty submitted thread projections', () => {
    const response = fixture.threadResponse
    expect(
      writtenThreadResponseSchema.safeParse({
        ...response,
        thread: { ...response.thread, problemId: 'problem-another' },
      }).success,
    ).toBe(false)
    expect(
      writtenThreadResponseSchema.safeParse({
        ...response,
        thread: {
          ...response.thread,
          entries: [
            {
              ...response.thread.entries[0],
              text: ' ',
              attachments: [],
            },
          ],
        },
      }).success,
    ).toBe(false)
  })

  it('scopes query keys by principal and problem', () => {
    const first = { audience: 'student' as const, accountId: 'account-first' }
    const second = { audience: 'student' as const, accountId: 'account-second' }

    expect(writtenSubmissionQueryKeys.thread(first, 'problem-written-fixture')).not.toEqual(
      writtenSubmissionQueryKeys.thread(second, 'problem-written-fixture'),
    )
    expect(() => writtenSubmissionQueryKeys.thread(first, '../unsafe')).toThrow()
  })
})
