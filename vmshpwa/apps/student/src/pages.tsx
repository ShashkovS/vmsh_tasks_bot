import { Camera, MessageCircleQuestion, Send } from 'lucide-react'

import { MathDocument } from '@vmsh/content'
import { PrototypePage, type PrototypeCard } from '@vmsh/app-shell'
import { Button, Card, CardContent, CardHeader, CardTitle, Input, Textarea } from '@vmsh/ui'

const lessonCards: PrototypeCard[] = [
  {
    title: '1. Разнообразные вагоны',
    description: 'Тестовая задача',
    meta: 'решено',
    status: 'success',
    action: 'Открыть',
  },
  {
    title: '6а. Расставьте 8 ладей',
    description: 'Письменное решение',
    meta: 'на проверке',
    status: 'info',
    action: 'Продолжить',
  },
  {
    title: '8. Пример на вычитание',
    description: 'Устная задача',
    meta: 'не открывалась',
    action: 'Открыть',
  },
]

export function StudentTodayPage() {
  return (
    <PrototypePage
      eyebrow="Урок 21 · начинающие"
      title="Текущая неделя"
      description="Условия уже опубликованы. Письменные ответы принимаются до воскресенья, 13:00 по вашему местному времени."
      actions={<Button>Продолжить задачу</Button>}
      cards={lessonCards}
    >
      <Card>
        <CardHeader>
          <CardTitle>Что дальше</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3 text-sm sm:grid-cols-3">
          <p>
            <strong>Суббота, 12:00</strong>
            <br />
            <span className="text-muted-foreground">откроются подсказки</span>
          </p>
          <p>
            <strong>Воскресенье, 13:00</strong>
            <br />
            <span className="text-muted-foreground">закроется приём</span>
          </p>
          <p>
            <strong>Воскресенье, 15:00</strong>
            <br />
            <span className="text-muted-foreground">откроются решения</span>
          </p>
        </CardContent>
      </Card>
    </PrototypePage>
  )
}

export function StudentTasksPage() {
  return (
    <PrototypePage
      eyebrow="Архив и текущий урок"
      title="Задачи"
      description="Переключайтесь между длинным листом и отдельными задачами."
      cards={lessonCards}
    />
  )
}

export function StudentTaskPage({ taskId }: { taskId: string }) {
  return (
    <PrototypePage
      eyebrow={`Задача ${taskId}`}
      title="Расставьте 8 ладей"
      description="Письменная задача · ответ можно исправлять после комментария учителя."
    >
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <Card>
          <CardContent className="pt-6">
            <MathDocument>
              <p>
                Расставьте на шахматной доске 8 ладей так, чтобы каждая ладья била ровно две другие.
                Объясните, почему ваша расстановка подходит.
              </p>
              <div
                className="my-6 grid aspect-square max-w-sm grid-cols-8 border"
                aria-label="Схема шахматной доски"
              >
                {Array.from({ length: 64 }, (_, index) => (
                  <span
                    className={(Math.floor(index / 8) + index) % 2 ? 'bg-muted' : 'bg-card'}
                    key={index}
                  />
                ))}
              </div>
            </MathDocument>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Ваше решение</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <Textarea placeholder="Напишите пояснение…" rows={7} />
            <Button variant="outline">
              <Camera /> Добавить фото
            </Button>
            <Button className="w-full">
              <Send /> Сдать решение
            </Button>
            <p className="text-xs text-muted-foreground">
              Без сети ответ будет поставлен в очередь и отправлен при подключении.
            </p>
          </CardContent>
        </Card>
      </div>
    </PrototypePage>
  )
}

export function StudentSubmissionPage({ submissionId }: { submissionId: string }) {
  return (
    <PrototypePage
      eyebrow={`Сдача ${submissionId}`}
      title="Обсуждение решения"
      description="Учитель отметил фрагмент на второй фотографии и ждёт исправление."
      cards={[
        {
          title: 'Комментарий учителя',
          description: 'Здесь нужно объяснить, почему ладьи в соседних строках не бьют друг друга.',
          meta: '10 минут назад',
          status: 'warning',
          action: 'Ответить',
        },
      ]}
    />
  )
}

export function StudentNewsPage() {
  return (
    <PrototypePage
      eyebrow="Telegram-канал и локальные объявления"
      title="Новости"
      description="Публикации сохранены в приложении и доступны после синхронизации."
      cards={[
        {
          title: 'Условия 21-го занятия',
          description: 'Задачи трёх уровней опубликованы. Удачной работы!',
          meta: 'понедельник, 16:30',
          status: 'info',
          action: 'Читать',
        },
        {
          title: 'Подсказки откроются в субботу',
          description: 'Сначала попробуйте ещё один подход самостоятельно.',
          meta: 'вчера',
          action: 'Читать',
        },
      ]}
    />
  )
}

export function StudentNewsDetailPage({ postId }: { postId: string }) {
  return (
    <PrototypePage
      eyebrow={`Публикация ${postId}`}
      title="Условия 21-го занятия"
      description="Зеркальная копия публикации Telegram с локально сохранёнными медиа."
    >
      <Card>
        <CardContent className="space-y-3 pt-6 font-reading leading-7">
          <p>Новый листок уже доступен. Начните с тестовых задач, затем переходите к письменным.</p>
          <p>Если возник вопрос, задайте его прямо из карточки задачи.</p>
        </CardContent>
      </Card>
    </PrototypePage>
  )
}

export function StudentProgressPage() {
  return (
    <PrototypePage
      eyebrow="Без сравнения с другими"
      title="Ваш прогресс"
      description="Личная динамика, завершённость и первые спокойные достижения."
      cards={[
        { title: '17 задач', description: 'Решено за последние четыре занятия', status: 'success' },
        {
          title: 'Первый письменный плюс',
          description: 'Достижение получено на 20-м занятии',
          status: 'info',
        },
        {
          title: 'Серия: 3 недели',
          description: 'Вы сдавали хотя бы одну задачу каждую неделю',
          status: 'warning',
        },
      ]}
    />
  )
}

export function StudentProfilePage() {
  return (
    <PrototypePage
      eyebrow="Профиль"
      title="Василий Петров"
      description="Начинающие · очное участие"
      cards={[
        {
          title: 'Режим участия',
          description: 'Очно. Это значение также могут изменить опекун, учитель или администратор.',
          action: 'Изменить',
        },
        {
          title: 'Устройства',
          description: 'iPhone · текущая сессия действует до 10 августа',
          action: 'Управлять',
        },
        {
          title: 'Помощь',
          description: 'Общий вопрос учителям без привязки к задаче',
          action: 'Задать вопрос',
        },
      ]}
    />
  )
}

export function StudentNotificationsPage() {
  return (
    <PrototypePage
      eyebrow="Профиль"
      title="Уведомления"
      description="Настройте системные push-уведомления по категориям."
      cards={[
        { title: 'Результаты проверки', description: 'Включено', status: 'success' },
        { title: 'Ответы учителей', description: 'Включено', status: 'success' },
        { title: 'Новости и подсказки', description: 'Выключено' },
        { title: 'Очные приглашения', description: 'Включено', status: 'success' },
      ]}
    />
  )
}

export function StudentLoginPage() {
  return (
    <PrototypePage
      eyebrow="Вход"
      title="Личный кабинет школьника"
      description="Введите логин и ваш текущий токен Telegram-бота."
    >
      <Card className="max-w-md">
        <CardContent className="space-y-4 pt-6">
          <Input autoComplete="username" placeholder="Логин" />
          <Input autoComplete="current-password" placeholder="Пароль" type="password" />
          <Button className="w-full">Войти</Button>
          <Button className="w-full" variant="ghost">
            <MessageCircleQuestion /> Не получается войти
          </Button>
        </CardContent>
      </Card>
    </PrototypePage>
  )
}
