import { Bell, Check, Users } from 'lucide-react'

import { MathDocument } from '@vmsh/content'
import { PrototypePage } from '@vmsh/app-shell'
import { Button, Card, CardContent, Input, Switch } from '@vmsh/ui'

export function FamilyHomePage() {
  return (
    <PrototypePage
      eyebrow="Василий · начинающие"
      title="Текущее занятие"
      description="Постоянный режим: очно. Последняя активность ребёнка — 10 часов назад."
      actions={<Button variant="outline">Сменить ребёнка</Button>}
      cards={[
        {
          title: '5 задач сдано',
          description: 'Три тестовые и две письменные',
          status: 'success',
          action: 'Подробнее',
        },
        {
          title: '3 ответа на проверке',
          description: 'Учителя ещё не взяли две работы',
          status: 'info',
          action: 'Посмотреть',
        },
        {
          title: '2 неверные попытки',
          description: 'Можно попробовать снова до закрытия приёма',
          status: 'warning',
          action: 'К задачам',
        },
      ]}
    />
  )
}

export function FamilyChildrenPage() {
  return (
    <PrototypePage
      eyebrow="Семья"
      title="Связанные дети"
      description="Один опекун может видеть нескольких детей; связь создаёт администратор."
      cards={[
        {
          title: 'Василий Петров',
          description: 'Начинающие · очно',
          status: 'success',
          action: 'Открыть',
        },
        {
          title: 'Мария Петрова',
          description: 'Продолжающие · online',
          status: 'info',
          action: 'Открыть',
        },
      ]}
    />
  )
}

export function FamilyChildPage({ childId }: { childId: string }) {
  return (
    <PrototypePage
      eyebrow={`Профиль ${childId}`}
      title="Василий Петров"
      description="Обзор участия и учебной активности."
    >
      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardContent className="space-y-4 pt-6">
            <div className="flex items-center justify-between gap-4">
              <div>
                <strong>Очное участие</strong>
                <p className="text-sm text-muted-foreground">Постоянный профиль</p>
              </div>
              <Switch defaultChecked aria-label="Очное участие" />
            </div>
            <p className="text-xs text-muted-foreground">
              Изменение будет видно ребёнку, учителям и администраторам. Автор сохранится в журнале.
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="space-y-2 pt-6 text-sm">
            <p>
              <strong>Первое открытие:</strong> вторник, 17:42
            </p>
            <p>
              <strong>Последняя активность:</strong> 10 часов назад
            </p>
            <p>
              <strong>Текущий результат:</strong> 5 решено, 3 на проверке
            </p>
          </CardContent>
        </Card>
      </div>
    </PrototypePage>
  )
}

export function FamilyTaskPage({ taskId }: { taskId: string }) {
  return (
    <PrototypePage
      eyebrow={`Самостоятельное решение · ${taskId}`}
      title="Разнообразные вагоны"
      description="Ваши ответы не попадают учителям и не влияют на статистику ребёнка."
    >
      <div className="grid gap-4 lg:grid-cols-[1fr_22rem]">
        <Card>
          <CardContent className="pt-6">
            <MathDocument>
              <p>
                В поезде несколько красных, синих и зелёных вагонов. По условию определите число
                красных вагонов.
              </p>
            </MathDocument>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="space-y-4 pt-6">
            <Input inputMode="numeric" placeholder="Ваш ответ" />
            <Button className="w-full">Проверить автоматически</Button>
            <Button className="w-full" variant="outline">
              <Check /> Сравнить с решением позже
            </Button>
          </CardContent>
        </Card>
      </div>
    </PrototypePage>
  )
}

export function FamilyNewsPage() {
  return (
    <PrototypePage
      eyebrow="Новости ВМШ 179"
      title="Объявления"
      description="Telegram-публикации и отдельные сообщения для семей."
      cards={[
        {
          title: 'Приглашаем Василия очно',
          description: 'Аудитория 215, второй этаж. Приходите к 16:35.',
          status: 'info',
          action: 'Подробнее',
        },
        {
          title: 'Условия 21-го занятия',
          description: 'Материалы нового урока опубликованы.',
          action: 'Читать',
        },
      ]}
    />
  )
}

export function FamilyNewsDetailPage({ postId }: { postId: string }) {
  return (
    <PrototypePage
      eyebrow={`Публикация ${postId}`}
      title="Очное занятие"
      description="Персональное приглашение сохранено в центре уведомлений."
    >
      <Card className="max-w-2xl">
        <CardContent className="space-y-3 pt-6">
          <p>Приглашаем Василия на очное занятие в аудиторию 215 на втором этаже.</p>
          <p className="text-sm text-muted-foreground">
            Начало в 16:40 по местному времени устройства.
          </p>
        </CardContent>
      </Card>
    </PrototypePage>
  )
}

export function FamilyProfilePage() {
  return (
    <PrototypePage
      eyebrow="Профиль опекуна"
      title="Сергей Петров"
      description="Отдельный семейный аккаунт без привязки к Telegram."
      cards={[
        { title: 'Связанные дети', description: '2 профиля', action: 'Управлять' },
        { title: 'Устройства', description: '1 активная сессия', action: 'Посмотреть' },
        { title: 'Помощь', description: 'Связаться с администраторами', action: 'Открыть' },
      ]}
    />
  )
}

export function FamilyNotificationsPage() {
  return (
    <PrototypePage
      eyebrow="Настройки"
      title="Уведомления"
      description="Категории можно включать независимо."
      cards={[
        { title: 'Очные приглашения', description: 'Включено', status: 'success' },
        { title: 'Активность ребёнка', description: 'Включено', status: 'success' },
        { title: 'Новости', description: 'Выключено' },
        { title: 'Дедлайны', description: 'Включено', status: 'success' },
      ]}
    />
  )
}

export function FamilyLoginPage() {
  return (
    <PrototypePage
      eyebrow="Семейный кабинет"
      title="Вход для опекуна"
      description="Этот аккаунт не связан с Telegram и не использует пароль ребёнка."
    >
      <Card className="max-w-md">
        <CardContent className="space-y-4 pt-6">
          <Input autoComplete="username" placeholder="Логин" />
          <Input autoComplete="current-password" placeholder="Пароль" type="password" />
          <Button className="w-full">
            <Users /> Войти
          </Button>
          <Button className="w-full" variant="ghost">
            <Bell /> Нужна помощь со входом
          </Button>
        </CardContent>
      </Card>
    </PrototypePage>
  )
}
