import { Activity, MousePointerClick, UsersRound } from 'lucide-react'
import { useMemo, useState } from 'react'

import {
  createProductAnalyticsClient,
  PageLayout,
  PageSection,
  PageStatePanel,
  useProductAnalyticsEvents,
  useProductAnalyticsSummary,
  useRuntimeConfig,
} from '@vmsh/app-shell'
import {
  Badge,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Input,
  Label,
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@vmsh/ui'

const DAY = 24 * 60 * 60 * 1000
const dateInput = (value: Date) => value.toISOString().slice(0, 10)

function Metric({
  icon: Icon,
  label,
  value,
}: {
  icon: typeof Activity
  label: string
  value: number
}) {
  return (
    <Card size="sm">
      <CardHeader className="flex-row items-center justify-between">
        <CardTitle className="text-caption font-medium text-muted-foreground">{label}</CardTitle>
        <Icon className="size-4 text-muted-foreground" />
      </CardHeader>
      <CardContent className="font-num text-title font-semibold">
        {value.toLocaleString('ru-RU')}
      </CardContent>
    </Card>
  )
}

export function ProductAnalyticsPage() {
  const runtime = useRuntimeConfig()
  const client = useMemo(() => createProductAnalyticsClient(runtime), [runtime])
  const [from, setFrom] = useState(() => dateInput(new Date(Date.now() - 14 * DAY)))
  const [to, setTo] = useState(() => dateInput(new Date()))
  const [audience, setAudience] = useState('')
  const [accountId, setAccountId] = useState('')
  const filter = {
    from: new Date(`${from}T00:00:00Z`).toISOString(),
    to: new Date(`${to}T23:59:59Z`).toISOString(),
    ...(audience ? { audience } : {}),
    ...(accountId.trim() ? { accountId: accountId.trim() } : {}),
  }
  const summary = useProductAnalyticsSummary(client, filter)
  const events = useProductAnalyticsEvents(client, filter)

  return (
    <PageLayout
      description="Компактная история просмотра страниц и завершённых действий. Данные хранятся до следующей границы учебного года."
      eyebrow="Только для глобального администратора"
      title="Аналитика"
    >
      <PageSection title="Период и фильтры">
        <div className="grid gap-3 md:grid-cols-4">
          <div>
            <Label htmlFor="analytics-from">С</Label>
            <Input
              id="analytics-from"
              onChange={(event) => setFrom(event.target.value)}
              type="date"
              value={from}
            />
          </div>
          <div>
            <Label htmlFor="analytics-to">По</Label>
            <Input
              id="analytics-to"
              onChange={(event) => setTo(event.target.value)}
              type="date"
              value={to}
            />
          </div>
          <div>
            <Label id="analytics-audience-label">Кабинет</Label>
            <Select
              onValueChange={(value) => setAudience(value === 'all' ? '' : (value ?? ''))}
              value={audience || 'all'}
            >
              <SelectTrigger aria-labelledby="analytics-audience-label">
                <SelectValue placeholder="Все" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Все</SelectItem>
                <SelectItem value="student">Школьник</SelectItem>
                <SelectItem value="family">Родитель</SelectItem>
                <SelectItem value="staff">Staff</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label htmlFor="analytics-user">ID пользователя</Label>
            <Input
              id="analytics-user"
              onChange={(event) => setAccountId(event.target.value)}
              placeholder="Например, u-2"
              value={accountId}
            />
          </div>
        </div>
      </PageSection>
      {summary.isPending ? (
        <PageStatePanel state="loading" title="Загружаем аналитику" />
      ) : summary.isError ? (
        <PageStatePanel state="error" title="Не удалось загрузить аналитику" />
      ) : summary.data ? (
        <>
          <section className="grid gap-3 sm:grid-cols-3">
            <Metric
              icon={UsersRound}
              label="Активные пользователи"
              value={summary.data.activeUsers}
            />
            <Metric icon={Activity} label="Просмотры" value={summary.data.pageViews} />
            <Metric icon={MousePointerClick} label="События" value={summary.data.actions} />
          </section>
          <PageSection title="Популярные маршруты">
            <div className="flex flex-wrap gap-2">
              {summary.data.popularRoutes.length ? (
                summary.data.popularRoutes.map((item) => (
                  <Badge key={item.routeId} variant="outline">
                    {item.routeId} · {item.count}
                  </Badge>
                ))
              ) : (
                <span className="text-muted-foreground">За выбранный период событий нет.</span>
              )}
            </div>
          </PageSection>
        </>
      ) : null}
      <PageSection title="Последние события">
        <div className="space-y-2">
          {events.isPending ? (
            <PageStatePanel state="loading" title="Загружаем ленту" />
          ) : events.isError ? (
            <PageStatePanel state="error" title="Не удалось загрузить ленту" />
          ) : events.data?.events.length ? (
            events.data.events.map((event) => (
              <Card key={event.eventId} size="sm">
                <CardContent className="grid gap-1 py-3 text-sm">
                  <div className="flex flex-wrap gap-x-2">
                    <strong>{event.account.displayName}</strong>
                    <span className="text-muted-foreground">
                      {event.account.currentAudience ?? 'удалён'} ·{' '}
                      {new Date(event.occurred_at).toLocaleString('ru-RU')}
                    </span>
                  </div>
                  <div>
                    <Badge variant="secondary">{event.audience}</Badge>{' '}
                    <code>{event.event_type}</code> · <code>{event.route_id}</code>
                  </div>
                  <div className="text-muted-foreground">
                    viewport {event.viewport_width}×{event.viewport_height}, DPR{' '}
                    {event.device_pixel_ratio}, {event.pointer_type}, {event.display_mode}
                    {event.entity_type ? ` · ${event.entity_type}: ${event.entity_public_id}` : ''}
                  </div>
                </CardContent>
              </Card>
            ))
          ) : (
            <PageStatePanel
              description="Измените период или фильтр."
              state="empty"
              title="Событий нет"
            />
          )}
        </div>
      </PageSection>
    </PageLayout>
  )
}
