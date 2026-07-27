import type { Meta, StoryObj } from '@storybook/react-vite'
import { expect, userEvent, within } from 'storybook/test'

import fixture from '@vmsh/contracts/fixtures/content/web-document.v1.json'
import { ContentNetworkError, type ContentApiClient } from '@vmsh/content'
import {
  ApiResponseError,
  contentEtagSchema,
  publishedContentSchema,
  staffContentHistorySchema,
  staffContentRevisionSchema,
  webContentDocumentSchema,
  type StaffContentHistory,
} from '@vmsh/contracts'

import { StaffContentWorkspace } from './content-page'
import { RevisionAssetsRecovery } from './revision-assets-recovery'

const revisionId = fixture.document.revisionId
const groupLessonId = 'group-lesson-41-n'
const webDocument = webContentDocumentSchema.parse(
  JSON.parse(
    JSON.stringify(fixture.document).replace(
      '/student/api/v1/content/assets/asset:53a5d2ba',
      '/content/geometry.svg',
    ),
  ),
)
const readyRevision = staffContentRevisionSchema.parse({
  revisionId,
  sourceId: 'content-source-41-condition',
  groupLessonId,
  courseId: 'course-math-5-7',
  groupId: 'group-beginner',
  kind: 'condition',
  logicalFilename: 'condition.tex',
  revisionNumber: 1,
  status: 'ready',
  version: 2,
  compileLeaseExpiresAt: null,
  compileAttempt: 1,
  sourceSha256: fixture.document.sourceSha256,
  parserVersion: 'vmsh-content-1',
  diagnostics: [
    {
      code: 'latex.layout_crosses_semantic_boundary',
      severity: 'warning',
      message: 'Команда вертикального отступа не влияет на смысл документа.',
      span: {
        source_name: 'condition.tex',
        start: { offset: 18, line: 3, column: 1 },
        end: { offset: 24, line: 3, column: 7 },
      },
      recovery: null,
    },
  ],
  missingAssets: [],
  requestId: 'storybook-content',
})

function storyClient(overrides: Partial<ContentApiClient> = {}): ContentApiClient {
  return {
    audience: 'staff',
    uploadSource(input) {
      return Promise.resolve({
        data: {
          ...readyRevision,
          kind: input.kind,
          status: 'uploaded',
          version: 1,
          compileAttempt: 0,
        },
        etag: contentEtagSchema.parse(`"${revisionId}:v1"`),
      })
    },
    compileRevision() {
      return Promise.resolve({
        data: readyRevision,
        etag: contentEtagSchema.parse(`"${revisionId}:v2"`),
      })
    },
    diagnostics() {
      return Promise.resolve({
        data: readyRevision,
        etag: contentEtagSchema.parse(`"${revisionId}:v2"`),
      })
    },
    revisionAssets(targetRevisionId) {
      return Promise.resolve({
        data: {
          revisionId: targetRevisionId,
          status: 'ready',
          version: 2,
          missingAssets: [],
          assets: [],
          requestId: 'storybook-assets',
        },
        etag: contentEtagSchema.parse(`"${targetRevisionId}:v2"`),
      })
    },
    uploadRevisionAsset() {
      return Promise.reject(new Error('В этом Storybook-сценарии нет недостающих ресурсов'))
    },
    preview(_revisionId, kind) {
      return Promise.resolve(
        kind === 'web'
          ? { revisionId, kind: 'web', document: webDocument }
          : {
              revisionId,
              kind: 'telegram',
              html: '<h2>Занятие 41</h2><p>Решите задачи.</p><tg-math>n^2</tg-math>',
            },
      )
    },
    history() {
      return Promise.resolve(
        staffContentHistorySchema.parse({
          groupLessonId,
          courseId: 'course-math-5-7',
          groupId: 'group-beginner',
          businessTimezone: 'Europe/Moscow',
          materials: ['condition', 'hint', 'solution'].map((kind) => ({
            kind,
            revisions: [],
            currentPublished: null,
            currentScheduled: null,
            publicationHistory: [],
          })),
          requestId: 'storybook-history',
        }),
      )
    },
    publish(input) {
      const scheduled = input.mode === 'schedule'
      return Promise.resolve({
        data: {
          publicationId: scheduled ? 'publication-scheduled-41' : 'publication-41',
          groupLessonId,
          revisionId,
          kind: input.kind,
          state: scheduled ? 'scheduled' : 'published',
          version: 1,
          scheduledAt: scheduled ? '2026-02-01T10:00:00Z' : null,
          publishedAt: scheduled ? null : '2026-01-26T13:00:00Z',
          hiddenAt: null,
          requestId: 'storybook-publish',
        },
        etag: contentEtagSchema.parse(
          scheduled ? '"publication-scheduled-41:v1"' : '"publication-41:v1"',
        ),
      })
    },
    rollback() {
      return Promise.reject(new Error('Для первого Storybook revision откат ещё недоступен'))
    },
    cancelScheduled() {
      return Promise.reject(new Error('В этом Storybook-сценарии расписание ещё не создано'))
    },
    hidePublished() {
      return Promise.reject(new Error('В этом Storybook-сценарии скрытие не выполняется'))
    },
    published() {
      return Promise.resolve(
        publishedContentSchema.parse({
          groupLessonId,
          courseId: 'course-math-5-7',
          groupId: 'group-beginner',
          kind: 'condition',
          publicationId: 'publication-41',
          publicationVersion: 1,
          publishedAt: '2026-01-26T13:00:00Z',
          revisionId,
          document: webDocument,
        }),
      )
    },
    ...overrides,
  }
}

function publishedHistory(
  publicationId: string,
  publishedRevisionId: string,
  version: number,
): StaffContentHistory {
  const publication = {
    publicationId,
    revisionId: publishedRevisionId,
    kind: 'condition' as const,
    state: 'published' as const,
    version,
    scheduledAt: null,
    publishedAt: '2026-01-26T13:00:00Z',
    hiddenAt: null,
    etag: contentEtagSchema.parse(`"${publicationId}:v${version}"`),
  }
  return staffContentHistorySchema.parse({
    groupLessonId,
    courseId: 'course-math-5-7',
    groupId: 'group-beginner',
    businessTimezone: 'Europe/Moscow',
    materials: [
      {
        kind: 'condition',
        revisions: [
          {
            ...readyRevision,
            etag: contentEtagSchema.parse(`"${revisionId}:v2"`),
          },
        ],
        currentPublished: publication,
        currentScheduled: null,
        publicationHistory: [publication],
      },
      {
        kind: 'hint',
        revisions: [],
        currentPublished: null,
        currentScheduled: null,
        publicationHistory: [],
      },
      {
        kind: 'solution',
        revisions: [],
        currentPublished: null,
        currentScheduled: null,
        publicationHistory: [],
      },
    ],
    requestId: `history-${version}`,
  })
}

function revisionHistoryScenario(): StaffContentHistory {
  const revision = (
    revisionPublicId: string,
    revisionNumber: number,
    status: 'uploaded' | 'compiling',
    lease: string | null,
  ) => ({
    ...readyRevision,
    revisionId: revisionPublicId,
    revisionNumber,
    status,
    version: status === 'uploaded' ? 1 : 2,
    compileLeaseExpiresAt: lease,
    compileAttempt: status === 'uploaded' ? 0 : 1,
    etag: contentEtagSchema.parse(`"${revisionPublicId}:v${status === 'uploaded' ? 1 : 2}"`),
  })
  return staffContentHistorySchema.parse({
    groupLessonId,
    courseId: 'course-math-5-7',
    groupId: 'group-beginner',
    businessTimezone: 'Europe/Moscow',
    materials: [
      {
        kind: 'condition',
        revisions: [
          revision(revisionId, 1, 'uploaded', null),
          revision('revision-expired-compile', 2, 'compiling', '2026-01-01T10:00:00Z'),
          revision('revision-active-compile', 3, 'compiling', '2099-01-01T10:00:00Z'),
        ],
        currentPublished: null,
        currentScheduled: null,
        publicationHistory: [],
      },
      ...(['hint', 'solution'] as const).map((kind) => ({
        kind,
        revisions: [],
        currentPublished: null,
        currentScheduled: null,
        publicationHistory: [],
      })),
    ],
    requestId: 'history-recovery',
  })
}

function missingAssetHistory(): StaffContentHistory {
  const missingRevision = {
    ...readyRevision,
    status: 'uploaded' as const,
    version: 1,
    compileAttempt: 0,
    missingAssets: ['figures/rook.png'],
    etag: contentEtagSchema.parse(`"${revisionId}:v1"`),
  }
  return staffContentHistorySchema.parse({
    groupLessonId,
    courseId: 'course-math-5-7',
    groupId: 'group-beginner',
    businessTimezone: 'Europe/Moscow',
    materials: [
      {
        kind: 'condition',
        revisions: [missingRevision],
        currentPublished: null,
        currentScheduled: null,
        publicationHistory: [],
      },
      ...(['hint', 'solution'] as const).map((kind) => ({
        kind,
        revisions: [],
        currentPublished: null,
        currentScheduled: null,
        publicationHistory: [],
      })),
    ],
    requestId: 'history-missing-asset',
  })
}

function rollbackHistory(): StaffContentHistory {
  const revisions = [1, 2, 3].map((revisionNumber) => {
    const revisionPublicId = `revision-ready-${revisionNumber}`
    return {
      ...readyRevision,
      revisionId: revisionPublicId,
      revisionNumber,
      version: 2,
      etag: contentEtagSchema.parse(`"${revisionPublicId}:v2"`),
    }
  })
  const publication = {
    publicationId: 'publication-current-rollback',
    revisionId: 'revision-ready-3',
    kind: 'condition' as const,
    state: 'published' as const,
    version: 4,
    scheduledAt: null,
    publishedAt: '2026-07-27T10:00:00Z',
    hiddenAt: null,
    etag: contentEtagSchema.parse('"publication-current-rollback:v4"'),
  }
  return staffContentHistorySchema.parse({
    groupLessonId,
    courseId: 'course-math-5-7',
    groupId: 'group-beginner',
    businessTimezone: 'Europe/Moscow',
    materials: [
      {
        kind: 'condition',
        revisions,
        currentPublished: publication,
        currentScheduled: null,
        publicationHistory: [publication],
      },
      ...(['hint', 'solution'] as const).map((kind) => ({
        kind,
        revisions: [],
        currentPublished: null,
        currentScheduled: null,
        publicationHistory: [],
      })),
    ],
    requestId: 'history-rollback',
  })
}

const meta = {
  title: 'Pages/Staff/Content publication',
  parameters: { layout: 'fullscreen' },
} satisfies Meta
export default meta
type Story = StoryObj<typeof meta>

export const UploadPreviewPublish: Story = {
  name: 'Upload → diagnostics → two previews → publish',
  render: () => <StaffContentWorkspace client={storyClient()} groupLessonId={groupLessonId} />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    const conditionInput = (await canvas.findAllByLabelText('LaTeX-файл'))[0]!
    await userEvent.upload(
      conditionInput,
      new File(['\\задача Загаданное число \\кзадача'], 'condition.tex', {
        type: 'text/plain',
      }),
    )
    await userEvent.click(
      canvas
        .getAllByRole('button', { name: 'Загрузить и проверить' })
        .find((button) => !button.hasAttribute('disabled'))!,
    )

    await expect(canvas.getByText('Занятие 41 · Начинающие')).toBeVisible()
    await expect(canvas.getByText(/3:1 · Команда вертикального отступа/)).toBeVisible()
    await expect(canvas.getByRole('heading', { name: 'PWA' })).toBeVisible()
    await expect(canvas.getByRole('heading', { name: 'Telegram Rich HTML' })).toBeVisible()
    await expect(canvas.getByText(/<tg-math>n\^2<\/tg-math>/)).toBeVisible()
    await userEvent.click(canvas.getByRole('button', { name: 'Опубликовать сейчас' }))
    await expect(canvas.getByText(/Опубликовать условие revision 1 сейчас/)).toBeVisible()
    await userEvent.click(canvas.getByRole('button', { name: 'Подтвердить' }))
    await expect(canvas.getByText('Опубликовано')).toBeVisible()
    await expect(canvas.getByText(`Публичная revision: ${revisionId}`)).toBeVisible()
    await userEvent.click(canvas.getByRole('button', { name: 'Скрыть опубликованное' }))
    await expect(canvas.getByText(/Скрыть опубликованное условие/)).toBeVisible()
    await userEvent.click(canvas.getByRole('button', { name: 'Отмена' }))
    await expect(canvas.getByRole('button', { name: 'Скрыть опубликованное' })).toBeVisible()
  },
}

export const ResumeInterruptedRevision: Story = {
  name: 'Reload → resume uploaded and expired compile',
  render: () => (
    <StaffContentWorkspace
      client={storyClient({ history: () => Promise.resolve(revisionHistoryScenario()) })}
      groupLessonId={groupLessonId}
    />
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await expect(
      await canvas.findByRole('button', { name: 'Продолжить проверку revision 1' }),
    ).toBeVisible()
    await expect(
      canvas.getByRole('button', { name: 'Продолжить проверку revision 2' }),
    ).toBeVisible()
    await expect(canvas.getByText(/Revision 3 проверяется/)).toBeVisible()
    await userEvent.click(canvas.getByRole('button', { name: 'Продолжить проверку revision 1' }))
    await expect(await canvas.findByRole('heading', { name: 'PWA' })).toBeVisible()
    await expect(canvas.getByRole('heading', { name: 'Telegram Rich HTML' })).toBeVisible()
  },
}

export const RecoverMissingAsset: Story = {
  name: 'Missing asset → reuse → recompile',
  render: () => {
    let compileCall = 0
    let assetAttached = false
    let compiledReady = false
    const missingRevision = staffContentRevisionSchema.parse({
      ...readyRevision,
      status: 'uploaded',
      version: 2,
      compileAttempt: 1,
      missingAssets: ['figures/rook.png'],
      requestId: 'storybook-missing-asset',
    })
    const attachedAsset = {
      assetId: 'asset-rook',
      contentSha256: 'b'.repeat(64),
      src: '/pwa-content-assets/asset-rook',
      mediaType: 'image/webp' as const,
      width: 1280,
      height: 720,
    }
    const client = storyClient({
      history: () => Promise.resolve(missingAssetHistory()),
      compileRevision() {
        compileCall += 1
        if (compileCall === 1) {
          return Promise.reject(
            new ApiResponseError(422, {
              error: {
                code: 'content_assets_missing',
                message: 'Прикрепите недостающие ресурсы',
                requestId: 'storybook-compile-missing',
                details: { missingAssets: ['figures/rook.png'] },
              },
            }),
          )
        }
        compiledReady = true
        return Promise.resolve({
          data: { ...readyRevision, version: 4 },
          etag: contentEtagSchema.parse(`"${revisionId}:v4"`),
        })
      },
      diagnostics() {
        return Promise.resolve({
          data: compiledReady
            ? { ...readyRevision, version: 4 }
            : assetAttached
              ? { ...missingRevision, version: 3, missingAssets: [] }
              : missingRevision,
          etag: contentEtagSchema.parse(
            `"${revisionId}:v${compiledReady ? 4 : assetAttached ? 3 : 2}"`,
          ),
        })
      },
      revisionAssets() {
        return Promise.resolve({
          data: {
            revisionId,
            status: 'uploaded',
            version: assetAttached ? 3 : 2,
            missingAssets: assetAttached ? [] : ['figures/rook.png'],
            assets: [
              {
                logicalName: 'figures/rook.png',
                sourceKind: 'figure',
                status: assetAttached ? ('attached' as const) : ('missing' as const),
                acceptedUploadKinds: ['raster', 'svg'],
                asset: assetAttached ? attachedAsset : null,
              },
            ],
            requestId: 'storybook-revision-assets',
          },
          etag: contentEtagSchema.parse(`"${revisionId}:v${assetAttached ? 3 : 2}"`),
        })
      },
      uploadRevisionAsset() {
        assetAttached = true
        return Promise.resolve({
          data: {
            revisionId,
            status: 'uploaded',
            version: 3,
            logicalName: 'figures/rook.png',
            sourceKind: 'figure',
            asset: attachedAsset,
            reused: true,
            requestId: 'storybook-asset-reused',
          },
          etag: contentEtagSchema.parse(`"${revisionId}:v3"`),
        })
      },
    })
    return <StaffContentWorkspace client={client} groupLessonId={groupLessonId} />
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await userEvent.click(
      await canvas.findByRole('button', { name: 'Продолжить проверку revision 1' }),
    )
    await expect(await canvas.findByText('figures/rook.png')).toBeVisible()
    await userEvent.upload(
      canvas.getByLabelText('Файл'),
      new File(['synthetic image'], 'rook.png', { type: 'image/png' }),
    )
    await expect(canvas.getByText('Выбран: rook.png')).toBeVisible()
    await userEvent.click(canvas.getByRole('button', { name: 'Загрузить' }))
    await expect(await canvas.findByText('Переиспользован')).toBeVisible()
    await userEvent.click(canvas.getByRole('button', { name: 'Повторить сборку материала' }))
    await expect(await canvas.findByRole('heading', { name: 'PWA' })).toBeVisible()
    await expect(canvas.queryByText('figures/rook.png')).not.toBeInTheDocument()
  },
}

export const AssetUploadErrorKeepsSelection: Story = {
  name: 'Asset upload error → keep file for retry',
  render: () => {
    const client = storyClient({
      revisionAssets() {
        return Promise.resolve({
          data: {
            revisionId,
            status: 'uploaded',
            version: 2,
            missingAssets: ['figures/rook.png'],
            assets: [
              {
                logicalName: 'figures/rook.png',
                sourceKind: 'figure',
                status: 'missing',
                acceptedUploadKinds: ['raster'],
                asset: null,
              },
            ],
            requestId: 'storybook-revision-assets-error',
          },
          etag: contentEtagSchema.parse(`"${revisionId}:v2"`),
        })
      },
      uploadRevisionAsset() {
        return Promise.reject(new ContentNetworkError({ cause: new TypeError('socket closed') }))
      },
    })
    return (
      <div className="max-w-2xl p-4">
        <RevisionAssetsRecovery
          client={client}
          onCompile={() => Promise.resolve()}
          revisionId={revisionId}
        />
      </div>
    )
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await userEvent.upload(
      await canvas.findByLabelText('Файл'),
      new File(['synthetic image'], 'rook.png', { type: 'image/png' }),
    )
    await userEvent.click(canvas.getByRole('button', { name: 'Загрузить' }))
    await expect(
      await canvas.findByText('Нет связи с сервером. Проверьте подключение и повторите действие.'),
    ).toBeVisible()
    await expect(canvas.getByText('Выбран: rook.png')).toBeVisible()
    await expect(canvas.getByRole('button', { name: 'Повторить' })).toBeEnabled()
  },
}

export const RollbackReadyHistory: Story = {
  name: 'Rollback → select any ready revision',
  render: () => {
    const client = storyClient({
      history: () => Promise.resolve(rollbackHistory()),
      rollback(_current, targetRevisionId) {
        return Promise.resolve({
          data: {
            publicationId: 'publication-after-rollback',
            groupLessonId,
            revisionId: targetRevisionId,
            kind: 'condition',
            state: 'published',
            version: 1,
            scheduledAt: null,
            publishedAt: '2026-07-28T10:00:00Z',
            hiddenAt: null,
            requestId: 'storybook-rollback',
          },
          etag: contentEtagSchema.parse('"publication-after-rollback:v1"'),
        })
      },
    })
    return <StaffContentWorkspace client={client} groupLessonId={groupLessonId} />
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    const selector = await canvas.findByLabelText('Revision для отката')
    await expect(selector).toHaveTextContent('Revision 2')
    await userEvent.click(selector)
    const body = within(canvasElement.ownerDocument.body)
    await userEvent.click(await body.findByRole('option', { name: /Revision 1/ }))
    await userEvent.click(canvas.getByRole('button', { name: 'Откатить опубликованное' }))
    await expect(canvas.getByText(/Вернуть опубликованный материал к revision 1/)).toBeVisible()
    await userEvent.click(canvas.getByRole('button', { name: 'Подтвердить' }))
    await expect(canvas.getByText('Публичная revision: revision-ready-1')).toBeVisible()
  },
}

export const ScheduleInBusinessTimezone: Story = {
  name: 'Schedule → authoritative lesson timezone',
  render: () => (
    <StaffContentWorkspace
      client={storyClient({
        history: () => Promise.resolve(publishedHistory('publication-current', revisionId, 1)),
      })}
      groupLessonId={groupLessonId}
    />
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    const dateInput = await canvas.findByLabelText('Опубликовать по расписанию')
    await userEvent.type(dateInput, '2026-02-01T13:00')
    await userEvent.click(canvas.getByRole('button', { name: 'Запланировать' }))
    await expect(canvas.getByText(/2026-02-01 13:00 \(Europe\/Moscow\)/)).toBeVisible()
    await userEvent.click(canvas.getByRole('button', { name: 'Подтвердить' }))
    await expect(canvas.getAllByText(/Europe\/Moscow/).length).toBeGreaterThanOrEqual(2)
  },
}

export const OptimisticConflictRefetch: Story = {
  name: 'Optimistic conflict → authoritative refetch',
  render: () => {
    let historyCall = 0
    const client = storyClient({
      history() {
        historyCall += 1
        return Promise.resolve(
          historyCall === 1
            ? publishedHistory('publication-before-conflict', revisionId, 1)
            : publishedHistory('publication-after-conflict', 'revision-after-conflict', 2),
        )
      },
      publish() {
        return Promise.reject(
          new ApiResponseError(409, {
            error: {
              code: 'version_conflict',
              message: 'Публикация уже изменилась',
              requestId: 'storybook-conflict',
            },
          }),
        )
      },
    })
    return <StaffContentWorkspace client={client} groupLessonId={groupLessonId} />
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await userEvent.click(await canvas.findByRole('button', { name: 'Опубликовать сейчас' }))
    await userEvent.click(canvas.getByRole('button', { name: 'Подтвердить' }))

    await expect(
      await canvas.findByText('Материал уже изменён. Обновляем версии и публикации…'),
    ).toBeVisible()
    await expect(
      await canvas.findByText('Публичная revision: revision-after-conflict'),
    ).toBeVisible()
  },
}
