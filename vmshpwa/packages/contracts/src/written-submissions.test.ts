import { describe, expect, it } from 'vitest'

import fixture from '../fixtures/submissions/written-thread.v1.json'

import {
  createWrittenAttachmentResponseSchema,
  createWrittenEntryRequestSchema,
  deleteWrittenAttachmentRequestSchema,
  mutateWrittenAttachmentsResponseSchema,
  previewWrittenMaterialReassignmentRequestSchema,
  previewWrittenMaterialReassignmentResponseSchema,
  reassignWrittenMaterialRequestSchema,
  reassignWrittenMaterialResponseSchema,
  reorderWrittenAttachmentsRequestSchema,
  replaceWrittenEntryRequestSchema,
  replaceWrittenEntryResponseSchema,
  staffWrittenAttachmentSchema,
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
    expect(
      replaceWrittenEntryRequestSchema.safeParse({
        ...fixture.replaceRequest,
        attachmentIds: ['attachment-one', 'attachment-one'],
      }).success,
    ).toBe(false)
  })

  it('keeps replacement target, optimistic versions and audit identity explicit', () => {
    expect(replaceWrittenEntryRequestSchema.parse(fixture.replaceRequest)).toEqual(
      fixture.replaceRequest,
    )
    expect(replaceWrittenEntryResponseSchema.parse(fixture.replaceResponse)).toEqual(
      fixture.replaceResponse,
    )
    expect(
      replaceWrittenEntryResponseSchema.safeParse({
        ...fixture.replaceResponse,
        replacedEntryId: fixture.replaceResponse.entry.entryId,
      }).success,
    ).toBe(false)
  })

  it('validates Staff preview, atomic reassignment and Student provenance', () => {
    const item = {
      entryId: fixture.submitResponse.entry.entryId,
      itemKind: 'entry_text' as const,
      attachmentId: null,
    }
    const previewRequest = {
      schemaVersion: 1 as const,
      sourceThreadId: fixture.submitResponse.threadId,
      targetProblemId: 'problem-written-target',
      items: [item],
    }
    expect(previewWrittenMaterialReassignmentRequestSchema.parse(previewRequest)).toEqual(
      previewRequest,
    )
    expect(
      previewWrittenMaterialReassignmentRequestSchema.safeParse({
        ...previewRequest,
        items: [item, item],
      }).success,
    ).toBe(false)
    expect(
      previewWrittenMaterialReassignmentRequestSchema.safeParse({
        ...previewRequest,
        items: [{ ...item, itemKind: 'attachment' }],
      }).success,
    ).toBe(false)

    const scope = {
      courseId: 'course-math',
      groupId: 'group-beginner',
      groupLessonId: 'group-lesson-41',
    }
    const previewResponse = {
      schemaVersion: 1 as const,
      studentId: 'user-student',
      source: {
        threadId: previewRequest.sourceThreadId,
        problemId: fixture.submitResponse.problemId,
        threadStatus: 'awaiting_review' as const,
        threadVersion: fixture.submitResponse.threadVersion,
        scope,
      },
      target: {
        threadId: null,
        problemId: previewRequest.targetProblemId,
        threadVersion: null,
        scope,
      },
      items: [
        {
          ...item,
          entryState: 'submitted' as const,
          text: fixture.submitResponse.entry.text,
          attachment: null,
          locked: false,
        },
      ],
      impact: {
        postReview: false,
        sourceEvidenceUnchanged: true as const,
        sourceVerdictUnchanged: true as const,
        targetRequiresReview: true as const,
        studentLabel: 'Перенесено преподавателем' as const,
      },
      requestId: 'request-reassignment-preview',
    }
    expect(previewWrittenMaterialReassignmentResponseSchema.parse(previewResponse)).toEqual(
      previewResponse,
    )

    const staffAttachment = {
      ...fixture.attachmentResponse.entry.attachments[0],
      mediaPath:
        '/staff/api/v1/thread-entries/written-entry-fixture-1/attachments/written-attachment-fixture-1/media',
    }
    expect(staffWrittenAttachmentSchema.parse(staffAttachment)).toEqual(staffAttachment)
    expect(
      previewWrittenMaterialReassignmentResponseSchema
        .parse({
          ...previewResponse,
          items: [
            {
              entryId: item.entryId,
              itemKind: 'attachment',
              attachmentId: staffAttachment.attachmentId,
              entryState: 'submitted',
              text: null,
              attachment: staffAttachment,
              locked: false,
            },
          ],
        })
        .items.at(0)?.attachment?.mediaPath,
    ).toBe(staffAttachment.mediaPath)
    expect(
      staffWrittenAttachmentSchema.safeParse(fixture.attachmentResponse.entry.attachments[0])
        .success,
    ).toBe(false)

    const request = {
      ...previewRequest,
      idempotencyKey: 'f9a98ed8-4c1a-4c5e-baf9-82e57c9fe234',
      expectedSourceThreadVersion: previewResponse.source.threadVersion,
      expectedTargetThreadVersion: null,
      reason: 'Работа приложена к соседней задаче.',
    }
    expect(reassignWrittenMaterialRequestSchema.parse(request)).toEqual(request)
    const response = {
      schemaVersion: 1 as const,
      reassignmentId: 'written-reassignment-1',
      source: {
        threadId: previewRequest.sourceThreadId,
        problemId: fixture.submitResponse.problemId,
        threadStatus: 'closed' as const,
        threadVersion: previewResponse.source.threadVersion + 1,
      },
      target: {
        threadId: 'written-thread-target',
        problemId: previewRequest.targetProblemId,
        threadStatus: 'awaiting_review' as const,
        threadVersion: 1,
      },
      items: [item],
      movedAt: '2026-09-20T13:05:00Z',
      studentLabel: 'Перенесено преподавателем' as const,
      requestId: 'request-reassignment-commit',
    }
    expect(reassignWrittenMaterialResponseSchema.parse(response)).toEqual(response)

    const projectedThread = {
      ...fixture.threadResponse,
      problemId: response.target.problemId,
      thread: {
        ...fixture.threadResponse.thread,
        threadId: response.target.threadId,
        problemId: response.target.problemId,
        entries: [
          {
            ...fixture.threadResponse.thread.entries[0],
            projection: {
              kind: 'staff_reassignment' as const,
              reassignmentIds: [response.reassignmentId],
              sourceThreadId: response.source.threadId,
              sourceProblemId: response.source.problemId,
              targetThreadId: response.target.threadId,
              targetProblemId: response.target.problemId,
              movedAt: response.movedAt,
            },
          },
        ],
      },
    }
    expect(writtenThreadResponseSchema.parse(projectedThread)).toEqual(projectedThread)
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

  it('validates complete reorder and delete mutation boundaries', () => {
    expect(reorderWrittenAttachmentsRequestSchema.parse(fixture.reorderRequest)).toEqual(
      fixture.reorderRequest,
    )
    expect(mutateWrittenAttachmentsResponseSchema.parse(fixture.reorderResponse)).toEqual(
      fixture.reorderResponse,
    )
    expect(deleteWrittenAttachmentRequestSchema.parse(fixture.deleteRequest)).toEqual(
      fixture.deleteRequest,
    )
    expect(mutateWrittenAttachmentsResponseSchema.parse(fixture.deleteResponse)).toEqual(
      fixture.deleteResponse,
    )
    expect(
      reorderWrittenAttachmentsRequestSchema.safeParse({
        ...fixture.reorderRequest,
        attachmentIds: ['written-attachment-fixture-1', 'written-attachment-fixture-1'],
      }).success,
    ).toBe(false)
    expect(
      deleteWrittenAttachmentRequestSchema.safeParse({
        ...fixture.deleteRequest,
        attachmentId: 'browser-must-not-control-path-identity',
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

  it('validates Student-visible reviews and keeps annotations on concrete evidence', () => {
    const entry = fixture.submitResponse.entry
    const annotation = {
      attachmentId: entry.attachments[0]!.attachmentId,
      schemaVersion: 1 as const,
      rotation: 90 as const,
      marks: [
        {
          markId: 'written-review-mark-one',
          kind: 'rectangle' as const,
          data: {
            x: 0.1,
            y: 0.2,
            width: 0.3,
            height: 0.2,
            strokeWidth: 0.008,
            color: 'red' as const,
          },
        },
      ],
    }
    const response = {
      ...fixture.threadResponse,
      thread: {
        ...fixture.threadResponse.thread,
        entries: [entry],
        reviews: [
          {
            reviewId: 'written-review-one',
            targetProblemId: fixture.threadResponse.problemId,
            verdict: 15,
            commentEntryId: 'written-review-comment-one',
            comment: 'Проверьте выделенный переход.',
            reviewerName: 'Ирина Соколова',
            source: 'staff' as const,
            evidenceEntryIds: [entry.entryId],
            annotations: [annotation],
            completedAt: '2026-09-21T10:00:00.000000Z',
          },
        ],
      },
    }

    expect(writtenThreadResponseSchema.parse(response)).toEqual(response)
    expect(
      writtenThreadResponseSchema.safeParse({
        ...response,
        thread: {
          ...response.thread,
          reviews: [
            {
              ...response.thread.reviews[0],
              annotations: [{ ...annotation, attachmentId: 'foreign-attachment' }],
            },
          ],
        },
      }).success,
    ).toBe(false)
    expect('internalReaction' in response.thread.reviews[0]!).toBe(false)
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
