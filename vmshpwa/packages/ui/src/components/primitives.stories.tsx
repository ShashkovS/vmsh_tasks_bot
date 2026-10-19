import type { Meta, StoryObj } from '@storybook/react-vite'
import { expect, userEvent, waitFor, within } from 'storybook/test'

import {
  Badge,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Checkbox,
  Drawer,
  DrawerContent,
  DrawerDescription,
  DrawerFooter,
  DrawerHeader,
  DrawerTitle,
  DrawerTrigger,
  Field,
  FieldDescription,
  FieldLabel,
  Input,
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
  Switch,
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
  Textarea,
  toast,
} from '@vmsh/ui'

function PrimitiveGallery() {
  return (
    <div className="mx-auto grid max-w-5xl gap-6 lg:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle>Действия и статусы</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-wrap items-center gap-3">
          <Button>Основное действие</Button>
          <Button variant="outline">Вторичное</Button>
          <Button variant="destructive">Удалить</Button>
          <Badge>Тест</Badge>
          <Badge variant="outline">На проверке</Badge>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Поля ответа</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <Field>
            <FieldLabel htmlFor="answer">Ответ</FieldLabel>
            <Input id="answer" placeholder="Введите натуральное число" />
            <FieldDescription>Например: 179</FieldDescription>
          </Field>
          <Textarea aria-label="Письменное решение" placeholder="Напишите объяснение…" />
          <div className="flex items-center gap-3">
            <Checkbox id="confirm" />
            <FieldLabel htmlFor="confirm">Проверил перед отправкой</FieldLabel>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-sm">Push-уведомления</span>
            <Switch aria-label="Push-уведомления" />
          </div>
        </CardContent>
      </Card>
      <Card className="lg:col-span-2">
        <CardContent className="pt-6">
          {/*
            Tabs фильтруют список — это допустимое использование. Условие задачи
            НИКОГДА не прячется во вкладку: подсказка и решение раскрываются
            дополнительно под условием, а не заменяют его.
          */}
          <Tabs defaultValue="all">
            <TabsList>
              <TabsTrigger value="all">Все</TabsTrigger>
              <TabsTrigger value="todo">Нерешённые</TabsTrigger>
              <TabsTrigger value="review">На проверке</TabsTrigger>
            </TabsList>
            <TabsContent value="all">Показаны все задачи листка.</TabsContent>
            <TabsContent value="todo">Показаны только нерешённые задачи.</TabsContent>
            <TabsContent value="review">Показаны задачи, ожидающие проверки.</TabsContent>
          </Tabs>
        </CardContent>
      </Card>
      <Card className="lg:col-span-2">
        <CardHeader>
          <CardTitle>Временная обратная связь и выдвижная панель</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-3">
          <Button
            variant="outline"
            onClick={() =>
              toast.success('Черновик сохранён', 'Можно продолжить с другого устройства.')
            }
          >
            Показать уведомление
          </Button>
          <Drawer side="right">
            <DrawerTrigger render={<Button variant="outline" />}>Открыть панель</DrawerTrigger>
            <DrawerContent>
              <DrawerHeader>
                <DrawerTitle>Уведомления</DrawerTitle>
                <DrawerDescription>Выберите, о каких событиях вам сообщать.</DrawerDescription>
              </DrawerHeader>
              <div className="p-4 text-sm">Результаты проверки и новые комментарии включены.</div>
              <DrawerFooter>
                <Button>Сохранить</Button>
              </DrawerFooter>
            </DrawerContent>
          </Drawer>
        </CardContent>
      </Card>
      <Card className="lg:col-span-2">
        <CardContent className="pt-6">
          <Select>
            <SelectTrigger aria-label="Уровень">
              <SelectValue placeholder="Выберите уровень" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="n">Начинающие</SelectItem>
              <SelectItem value="p">Продолжающие</SelectItem>
              <SelectItem value="e">Эксперты</SelectItem>
            </SelectContent>
          </Select>
        </CardContent>
      </Card>
    </div>
  )
}

const meta = { title: 'UI/Primitives', component: PrimitiveGallery } satisfies Meta<
  typeof PrimitiveGallery
>
export default meta
type Story = StoryObj<typeof meta>

export const Gallery: Story = {
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await userEvent.type(canvas.getByLabelText('Ответ'), '179')
    await expect(canvas.getByLabelText('Ответ')).toHaveValue('179')
    await userEvent.click(canvas.getByLabelText('Push-уведомления'))
    await expect(canvas.getByLabelText('Push-уведомления')).toBeChecked()
    await userEvent.click(canvas.getByRole('button', { name: 'Показать уведомление' }))
    await waitFor(async () => {
      await expect(
        within(canvasElement.ownerDocument.body).getByText('Черновик сохранён'),
      ).toBeVisible()
    })
    await userEvent.click(canvas.getByRole('button', { name: 'Открыть панель' }))
    await waitFor(async () => {
      await expect(
        within(canvasElement.ownerDocument.body).getByRole('heading', { name: 'Уведомления' }),
      ).toBeVisible()
    })
  },
}
