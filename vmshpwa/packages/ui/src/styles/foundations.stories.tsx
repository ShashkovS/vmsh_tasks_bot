import type { Meta, StoryObj } from '@storybook/react-vite'

import { Badge, Card, CardContent } from '@vmsh/ui'

function FoundationPreview() {
  return (
    <div className="mx-auto max-w-5xl space-y-8">
      <header>
        <p className="text-xs font-medium tracking-wide text-primary uppercase">
          Art direction placeholder
        </p>
        <h1 className="mt-1 text-3xl font-semibold">Тихая редакционная среда</h1>
        <p className="mt-2 max-w-2xl text-muted-foreground">
          Эта страница проверяет структуру foundation story. Итоговый бренд, шрифты и палитра
          создаются только после approval фазы 1.
        </p>
      </header>
      <div className="grid gap-3 sm:grid-cols-3">
        <Card className="border-l-4 border-l-level-novice">
          <CardContent className="pt-6">
            <Badge variant="outline">Начинающие</Badge>
            <p className="mt-3 font-reading text-lg">Сколько квадратов на рисунке?</p>
          </CardContent>
        </Card>
        <Card className="border-l-4 border-l-level-continuing">
          <CardContent className="pt-6">
            <Badge variant="outline">Продолжающие</Badge>
            <p className="mt-3 font-reading text-lg">Докажите, что число делится на 7.</p>
          </CardContent>
        </Card>
        <Card className="border-l-4 border-l-level-expert">
          <CardContent className="pt-6">
            <Badge variant="outline">Эксперты</Badge>
            <p className="mt-3 font-reading text-lg">Найдите все натуральные решения.</p>
          </CardContent>
        </Card>
      </div>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        {[
          ['Успех', 'bg-status-success text-status-success-foreground'],
          ['Внимание', 'bg-status-warning text-status-warning-foreground'],
          ['Информация', 'bg-status-info text-status-info-foreground'],
          ['Ошибка', 'bg-destructive text-destructive-foreground'],
        ].map(([label, className]) => (
          <div className={`${className} rounded-md p-4 text-center text-sm`} key={label}>
            {label}
          </div>
        ))}
      </div>
    </div>
  )
}

const meta = { title: 'Foundations/Semantic tokens', component: FoundationPreview } satisfies Meta<
  typeof FoundationPreview
>
export default meta
type Story = StoryObj<typeof meta>

export const Light: Story = { globals: { theme: 'light' } }
export const Dark: Story = { globals: { theme: 'dark' } }
