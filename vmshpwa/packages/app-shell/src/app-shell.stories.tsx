import type { Meta, StoryObj } from '@storybook/react-vite'
import { expect, within } from 'storybook/test'
import {
  createMemoryHistory,
  createRootRoute,
  createRoute,
  createRouter,
  Outlet,
  RouterProvider,
} from '@tanstack/react-router'
import { BookOpenText, House, Newspaper, UserRound } from 'lucide-react'
import type { ReactNode } from 'react'

import { Card, CardContent, Skeleton } from '@vmsh/ui'

import { AppShell, type AppShellProps } from './app-shell'
import { PrototypePage } from './prototype-page'

function createShellRouter(
  product: AppShellProps['product'],
  title: string,
  mobileNavigation: boolean,
) {
  const navigation = [
    { label: 'Сейчас', to: '/', icon: <House className="size-4" aria-hidden="true" /> },
    {
      label: product === 'staff' ? 'Проверка' : 'Задачи',
      to: '/tasks',
      icon: <BookOpenText className="size-4" aria-hidden="true" />,
    },
    { label: 'Новости', to: '/news', icon: <Newspaper className="size-4" aria-hidden="true" /> },
    { label: 'Профиль', to: '/profile', icon: <UserRound className="size-4" aria-hidden="true" /> },
  ]
  const rootRoute = createRootRoute({
    component: () => (
      <AppShell
        product={product}
        title={title}
        displayName={
          product === 'student'
            ? 'Анна Иванова'
            : product === 'family'
              ? 'Мария Иванова'
              : 'Сергей Шашков'
        }
        navigation={navigation}
        mobileNavigation={mobileNavigation}
      >
        <Outlet />
      </AppShell>
    ),
  })
  const indexRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: '/',
    component: () => (
      <PrototypePage
        eyebrow="Урок 21 · прототип"
        title={product === 'staff' ? 'Рабочая сводка' : 'Текущая неделя'}
        description="Одинаковый каркас показывает различие мобильной и постоянной компактной навигации."
        cards={[
          {
            title: 'Разнообразные вагоны',
            description: 'Тестовая задача',
            meta: 'решено',
            status: 'success',
          },
          {
            title: 'Расставьте восемь ладей',
            description: 'Письменное решение',
            meta: 'на проверке',
            status: 'info',
          },
        ]}
      />
    ),
  })
  return createRouter({
    routeTree: rootRoute.addChildren([indexRoute]),
    history: createMemoryHistory({ initialEntries: ['/'] }),
  })
}

const studentRouter = createShellRouter('student', 'Школьник', true)
const familyRouter = createShellRouter('family', 'Семья', true)
const staffRouter = createShellRouter('staff', 'Учитель и администратор', false)

function ShellPreview({ audience }: { audience: 'student' | 'family' | 'staff' }) {
  return (
    <RouterProvider
      router={
        audience === 'student' ? studentRouter : audience === 'family' ? familyRouter : staffRouter
      }
    />
  )
}

const meta = {
  title: 'Product/App shells',
  component: ShellPreview,
  parameters: { layout: 'fullscreen' },
  play: async ({ canvasElement, args }) => {
    const header = within(canvasElement).getByRole('banner')
    await expect(
      within(header).getByText(
        args.audience === 'student'
          ? 'Анна Иванова'
          : args.audience === 'family'
            ? 'Мария Иванова'
            : 'Сергей Шашков',
      ),
    ).toBeVisible()
  },
} satisfies Meta<typeof ShellPreview>
export default meta
type Story = StoryObj<typeof meta>

export const StudentMobile: Story = {
  args: { audience: 'student' },
  parameters: { viewport: { defaultViewport: 'mobile2' } },
}

export const FamilyMobile: Story = {
  args: { audience: 'family' },
  parameters: { viewport: { defaultViewport: 'mobile2' } },
}

export const StaffDesktop: Story = { args: { audience: 'staff' } }

function StateGallery() {
  return (
    <div className="mx-auto grid max-w-5xl gap-4 md:grid-cols-2">
      <Card>
        <CardContent className="space-y-3 pt-6" role="status" aria-label="Загрузка">
          <Skeleton className="h-5 w-2/5" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-4/5" />
        </CardContent>
      </Card>
      <StateCard title="Здесь пока ничего нет">
        Новый листок появится в понедельник в 16:30.
      </StateCard>
      <StateCard title="Не удалось загрузить результаты" className="border-destructive">
        Ваш черновик сохранён. Повторите попытку, когда связь восстановится.
      </StateCard>
      <StateCard title="Вы не в сети · 2 отправки в очереди" className="border-status-warning">
        Можно продолжать работу. Мы покажем серверное подтверждение после синхронизации.
      </StateCard>
    </div>
  )
}

function StateCard({
  title,
  children,
  className,
}: {
  title: string
  children: ReactNode
  className?: string
}) {
  return (
    <Card className={className}>
      <CardContent className="pt-6">
        <h2 className="font-medium">{title}</h2>
        <p className="mt-2 text-sm text-muted-foreground">{children}</p>
      </CardContent>
    </Card>
  )
}

export const LoadingEmptyErrorOffline: Story = {
  args: { audience: 'student' },
  play: async () => {},
  render: () => <StateGallery />,
}
