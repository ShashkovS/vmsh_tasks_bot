import { Camera, FileUp, LockKeyhole, Send, Upload } from 'lucide-react'

import { PrototypePage } from '@vmsh/app-shell'
import {
  Badge,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Input,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
  Textarea,
} from '@vmsh/ui'

export function StaffHomePage() {
  return (
    <PrototypePage
      eyebrow="Понедельник · текущий цикл"
      title="Рабочая сводка"
      description="Компактный обзор публикации, проверки, очного потока и коммуникаций."
      actions={
        <>
          <Button variant="outline">Переключить режим</Button>
          <Button>Новая рассылка</Button>
        </>
      }
      cards={[
        {
          title: '43 работы в очереди',
          description: '7 уже взяты другими учителями',
          status: 'warning',
          action: 'К проверке',
        },
        {
          title: 'Урок 21 опубликован',
          description: 'Решения пока не загружены',
          status: 'success',
          action: 'Открыть',
        },
        {
          title: '186 очных участников',
          description: '12 пока без аудитории',
          status: 'info',
          action: 'Распределить',
        },
      ]}
    />
  )
}

export function ReviewQueuePage() {
  return (
    <PrototypePage
      eyebrow="Письменные задачи"
      title="Очередь проверки"
      description="Взятая работа мгновенно исчезает у остальных учителей."
      cards={[
        {
          title: 'Петров Василий · 21н.6а',
          description: '2 фотографии · первая сдача',
          meta: '12 минут',
          status: 'warning',
          action: 'Взять',
        },
        {
          title: 'Смирнова Анна · 21п.7',
          description: 'Исправление после комментария',
          meta: '18 минут',
          status: 'info',
          action: 'Взять',
        },
        {
          title: 'Ким Иван · 21э.6',
          description: 'Текст и 1 фотография',
          meta: '24 минуты',
          action: 'Взять',
        },
      ]}
    />
  )
}

export function ReviewWorkspacePage({ submissionId }: { submissionId: string }) {
  return (
    <div className="grid min-h-[calc(100svh-3.5rem)] grid-cols-[15rem_minmax(28rem,1fr)_20rem]">
      <aside className="border-r p-3">
        <p className="mb-3 text-xs font-medium text-muted-foreground uppercase">Очередь</p>
        {['Петров · 21н.6а', 'Смирнова · 21п.7', 'Ким · 21э.6'].map((item, index) => (
          <button
            className={`mb-1 w-full rounded-md p-2 text-left text-xs ${index === 0 ? 'bg-accent' : 'hover:bg-muted'}`}
            key={item}
          >
            {item}
          </button>
        ))}
      </aside>
      <section className="min-w-0 p-4">
        <div className="mb-3 flex items-center justify-between">
          <div>
            <Badge variant="outline">{submissionId}</Badge>
            <h1 className="mt-1 font-semibold">Расставьте 8 ладей</h1>
          </div>
          <Button variant="outline">
            <LockKeyhole /> Работа взята вами
          </Button>
        </div>
        <div className="relative flex min-h-[36rem] items-center justify-center rounded-lg border bg-muted">
          <Camera className="size-16 text-muted-foreground" aria-hidden="true" />
          <span
            className="absolute left-1/3 top-1/3 size-24 rounded-full border-4 border-destructive/70"
            aria-label="Аннотация учителя"
          />
        </div>
        <div className="mt-3 flex gap-2">
          <Button variant="outline">Перо</Button>
          <Button variant="outline">Комментарий к области</Button>
          <Button variant="ghost">Повернуть</Button>
        </div>
      </section>
      <aside className="border-l p-4">
        <h2 className="font-semibold">Обсуждение</h2>
        <div className="my-4 rounded-lg bg-muted p-3 text-sm">
          Поясните, почему ладьи в соседних строках не бьют друг друга.
        </div>
        <Textarea placeholder="Комментарий школьнику" rows={5} />
        <div className="mt-3 grid grid-cols-2 gap-2">
          <Button variant="outline">На доработку</Button>
          <Button>Плюс</Button>
        </div>
      </aside>
    </div>
  )
}

export function StaffLessonsPage() {
  return (
    <PrototypePage
      eyebrow="LaTeX — единственный источник"
      title="Уроки и публикации"
      description="Условия и решения загружаются независимо, по одному уровню или массово."
      actions={
        <Button>
          <FileUp /> Загрузить LaTeX
        </Button>
      }
      cards={[
        {
          title: '21 · начинающие',
          description: 'Условия опубликованы · решения не загружены',
          status: 'warning',
          action: 'Открыть',
        },
        {
          title: '21 · продолжающие',
          description: 'Условия опубликованы · 2 missing assets',
          status: 'info',
          action: 'Исправить',
        },
        { title: '21 · эксперты', description: 'Черновик новой версии', action: 'Preview' },
      ]}
    />
  )
}

export function StaffLessonDetailPage({ lessonId }: { lessonId: string }) {
  return (
    <PrototypePage
      eyebrow={`Урок ${lessonId}`}
      title="Импорт и метаданные"
      description="Сначала парсится LaTeX, затем система запрашивает только отсутствующие изображения."
      actions={
        <>
          <Button variant="outline">
            <Upload /> Новый файл
          </Button>
          <Button>Опубликовать уровень</Button>
        </>
      }
    >
      <div className="grid gap-4 xl:grid-cols-[20rem_1fr]">
        <Card>
          <CardHeader>
            <CardTitle>Диагностика</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <p className="text-status-success">✓ 12 задач распознано</p>
            <p className="text-status-success">✓ 8 старых изображений найдено</p>
            <p className="text-destructive">× diagram-21-7.pdf отсутствует</p>
            <Button className="w-full" variant="outline">
              Загрузить недостающие
            </Button>
          </CardContent>
        </Card>
        <MetadataGrid />
      </div>
    </PrototypePage>
  )
}

function MetadataGrid() {
  const rows = [
    ['н', '21', '1', '', 'Разнообразные вагоны', 'Тест', 'Натуральное', '6'],
    ['н', '21', '6', 'а', 'Расставьте 8 ладей', 'Письменно', '', ''],
    ['н', '21', '8', '', 'Пример на вычитание', 'Устно', '', ''],
  ]
  return (
    <Card className="overflow-hidden">
      <div className="flex items-center justify-between border-b p-3">
        <div>
          <strong className="text-sm">Метаданные задач</strong>
          <p className="text-xs text-muted-foreground">Поддерживается вставка и копирование TSV</p>
        </div>
        <Button size="sm" variant="outline">
          Вставить таблицу
        </Button>
      </div>
      <Table>
        <TableHeader>
          <TableRow>
            {['Группа', 'Листок', 'Задача', 'Пункт', 'Название', 'Тип', 'Ответ', 'Правильный'].map(
              (head) => (
                <TableHead key={head}>{head}</TableHead>
              ),
            )}
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((row) => (
            <TableRow key={row.join('-')}>
              {row.map((cell, index) => (
                <TableCell className={index === 4 ? 'min-w-52' : undefined} key={index}>
                  {cell || '—'}
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Card>
  )
}

export function StaffGenericPage({ title, description }: { title: string; description: string }) {
  return (
    <PrototypePage
      eyebrow="Teacher/Admin SPA"
      title={title}
      description={description}
      cards={[
        {
          title: 'Рабочее состояние',
          description: 'Реалистичная заглушка маршрута готова для следующей дизайн-фазы.',
          status: 'info',
        },
        {
          title: 'Пустое состояние',
          description: 'Будет документировано в Storybook вместе с ошибками и загрузкой.',
        },
      ]}
    />
  )
}

export function StaffLoginPage() {
  return (
    <PrototypePage
      eyebrow="Staff"
      title="Вход для учителя или администратора"
      description="Учитель видит только разрешённые группы."
    >
      <Card className="max-w-md">
        <CardContent className="space-y-4 pt-6">
          <Input autoComplete="username" placeholder="Логин" />
          <Input autoComplete="current-password" placeholder="Пароль" type="password" />
          <Button className="w-full">Войти</Button>
        </CardContent>
      </Card>
    </PrototypePage>
  )
}

export function BroadcastComposerPage() {
  return (
    <PrototypePage
      eyebrow="PWA и Telegram"
      title="Рассылки"
      description="Персональные сообщения и служебные уведомления создаются в SPA; новости канала зеркалируются отдельно."
    >
      <Card className="max-w-3xl">
        <CardContent className="space-y-4 pt-6">
          <Input placeholder="Получатели: группы, режим, аудитория…" />
          <Textarea placeholder="Текст сообщения с форматированием и математикой" rows={8} />
          <div className="flex justify-end">
            <Button>
              <Send /> Проверить и отправить
            </Button>
          </div>
        </CardContent>
      </Card>
    </PrototypePage>
  )
}
