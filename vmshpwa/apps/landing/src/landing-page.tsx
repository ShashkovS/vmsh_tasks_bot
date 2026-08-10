import { ArrowRight } from 'lucide-react'

import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Sign179,
  Wordmark,
  buttonVariants,
} from '@vmsh/ui'

const destinations = [
  {
    href: '/student/',
    title: 'Кабинет школьника',
    description: 'Задачи, сдача решений, проверки, новости и личный прогресс.',
  },
  {
    href: '/family/',
    title: 'Кабинет семьи',
    description: 'Активность ребёнка, результаты занятий и опубликованные новости.',
  },
] as const

/** Public entry page; it intentionally has no session, API or audience state. */
export function LandingPage() {
  return (
    <main className="min-h-svh bg-background text-foreground">
      <div className="mx-auto flex min-h-svh w-full max-w-5xl flex-col px-4 py-5 sm:px-8 sm:py-8">
        <header className="flex items-center gap-3" aria-label="ВМШ 179">
          <Sign179 className="text-primary" size={34} title="Знак ВМШ 179" />
          <Wordmark className="text-foreground" size={25} />
        </header>

        <section className="flex flex-1 flex-col justify-center py-14 sm:py-20">
          <p className="mb-4 text-sm font-medium tracking-wide text-primary uppercase">
            Математика · обучение · общение
          </p>
          <h1 className="max-w-3xl text-4xl leading-tight font-semibold tracking-tight sm:text-6xl">
            Решаем задачи и учимся видеть в математике больше.
          </h1>
          <p className="mt-6 max-w-2xl text-lg leading-8 text-muted-foreground sm:text-xl">
            ВМШ 179 — математический кружок для школьников. Выберите нужный кабинет, чтобы открыть
            задачи, результаты занятий и новости.
          </p>

          <div className="mt-10 grid gap-4 sm:grid-cols-2">
            {destinations.map((destination) => (
              <Card
                key={destination.href}
                className="border-border bg-surface shadow-(--elevation-1)"
              >
                <CardHeader>
                  <CardTitle className="text-xl">{destination.title}</CardTitle>
                </CardHeader>
                <CardContent className="flex h-full flex-col gap-6 pt-0">
                  <p className="flex-1 text-muted-foreground">{destination.description}</p>
                  <a
                    className={buttonVariants({ className: 'w-full sm:w-fit' })}
                    href={destination.href}
                  >
                    Открыть кабинет
                    <ArrowRight aria-hidden="true" />
                  </a>
                </CardContent>
              </Card>
            ))}
          </div>
        </section>

        <footer className="border-t border-border pt-4 text-sm text-muted-foreground">
          ВМШ 179 · математический кружок
        </footer>
      </div>
    </main>
  )
}
