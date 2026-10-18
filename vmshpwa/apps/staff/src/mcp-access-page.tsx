import { t } from '@lingui/core/macro'
import { Trans } from '@lingui/react/macro'
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useAuthenticatedPrincipal, PageLayout } from '@vmsh/app-shell'
import { aiReviewTokensSchema, aiReviewTokenReceiptSchema } from '@vmsh/contracts'
import { currentLocale, dateTimeFormat } from '@vmsh/i18n'
import { Button, Input } from '@vmsh/ui'
import { useAiReviewRequest } from './ai-review-client'

/** Personal token lifecycle; docs/ai-review-assistant.md, cookie-only API. */
export function McpAccessPage() {
  const principal = useAuthenticatedPrincipal()
  const request = useAiReviewRequest()
  const [name, setName] = useState('')
  const [secret, setSecret] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(false)
  const query = useQuery({
    queryKey: ['ai-review-tokens', principal.accountId],
    queryFn: async ({ signal }) =>
      aiReviewTokensSchema.parse(await request('/ai-review/tokens', { signal })),
  })
  const mutate = async (tokenId?: string) => {
    setBusy(true)
    setError(false)
    try {
      if (tokenId) {
        await request(`/ai-review/tokens/${encodeURIComponent(tokenId)}`, { method: 'DELETE' })
      } else {
        const receipt = aiReviewTokenReceiptSchema.parse(
          await request('/ai-review/tokens', {
            method: 'POST',
            body: JSON.stringify({ name: name.trim() }),
          }),
        )
        setSecret(receipt.secret)
        setName('')
      }
      await query.refetch()
    } catch {
      setError(true)
    } finally {
      setBusy(false)
    }
  }
  return (
    <PageLayout title={t`MCP-доступ`}>
      <div className="max-w-2xl space-y-4">
        <p className="text-small">
          <Trans>
            Токен открывает учебные материалы ваших кружков и групп, включая неопубликованные
            решения и изображения из диалогов. Через него можно загружать приватные предложения ИИ
            для учителя.
          </Trans>
        </p>
        <p className="text-small">
          <Trans>
            Срок действия — 90 дней. Сохраните секрет при создании: повторно он не показывается.
          </Trans>
        </p>
        <form
          className="flex flex-wrap items-end gap-2"
          onSubmit={(event) => {
            event.preventDefault()
            if (!busy && name.trim()) void mutate()
          }}
        >
          <label htmlFor="mcp-connection-name" className="space-y-1 text-small">
            <span className="block">
              <Trans>Название подключения</Trans>
            </span>
            <Input
              id="mcp-connection-name"
              value={name}
              maxLength={100}
              onChange={(event) => setName(event.target.value)}
            />
          </label>
          <Button type="submit" disabled={busy || !name.trim()}>
            <Trans>Создать токен</Trans>
          </Button>
        </form>
        {secret && (
          <section
            className="space-y-2 rounded-lg border border-border p-3"
            aria-label={t`Новый токен`}
          >
            <p className="text-small">
              <Trans>Сохраните этот секрет в настройках MCP-клиента.</Trans>
            </p>
            <code className="block break-all select-all text-small">{secret}</code>
            <Button variant="outline" onClick={() => setSecret(null)}>
              <Trans>Скрыть секрет</Trans>
            </Button>
          </section>
        )}
        {(error || query.isError) && (
          <p role="alert">
            <Trans>Не удалось обновить MCP-доступ.</Trans>{' '}
            <Button variant="ghost" onClick={() => void query.refetch()}>
              <Trans>Повторить</Trans>
            </Button>
          </p>
        )}
        {query.isPending && (
          <p role="status">
            <Trans>Загружаем подключения…</Trans>
          </p>
        )}
        <ul className="space-y-3">
          {query.data?.items.map((token) => (
            <li
              key={token.tokenId}
              className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border p-3"
            >
              <div>
                <p className="text-label">{token.name}</p>
                <p className="text-caption text-muted-foreground">
                  {token.revokedAt ? t`Отозван` : t`Действует до`}{' '}
                  {!token.revokedAt &&
                    dateTimeFormat(currentLocale(), { dateStyle: 'medium' }).format(
                      new Date(token.expiresAt),
                    )}
                </p>
              </div>
              {!token.revokedAt && (
                <Button
                  variant="outline"
                  disabled={busy}
                  onClick={() => void mutate(token.tokenId)}
                >
                  <Trans>Отозвать</Trans>
                </Button>
              )}
            </li>
          ))}
        </ul>
      </div>
    </PageLayout>
  )
}
