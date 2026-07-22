/**
 * One scene, three directions. The content, the order of the blocks and the
 * viewport are identical for A, B and C on purpose: the gate chooses a visual
 * language, not a lucky screen. All text is real ВМШ 179 material (занятие 21н,
 * занятие 27х and the circle's Telegram channel).
 */
import { BookOpenText, House, Newspaper, TrendingUp, UserRound } from 'lucide-react'
import { createContext, useContext, useId, useState } from 'react'

import { directions, type DirectionId } from './directions'
import { AlbumThumb, ChessRooksFigure, NotebookPhoto, SymmetryFigure } from './figures'
import { M, MathDisplay } from './math'
import { markSets } from './marks'

export type Density = 'student' | 'family' | 'staff'

const levelNames: Record<0 | 1 | 2 | 3, string> = {
  0: 'Тестирование',
  1: 'Начинающие',
  2: 'Продолжающие',
  3: 'Эксперты',
}

/** Short codes used by the circle itself: 21н.6, 21п.4, 21х.2. */
const levelLetters: Record<0 | 1 | 2 | 3, string> = { 0: 'т', 1: 'н', 2: 'п', 3: 'х' }

export function LevelChip({ level }: { level: 0 | 1 | 2 | 3 }) {
  const bars = level === 0 ? 1 : level
  return (
    <span className="ad-level" data-level={level}>
      <span aria-hidden="true" className="ad-level__glyph">
        {[0, 1, 2].map((index) => (
          <i
            key={index}
            style={{
              height: `${index < bars ? 35 + index * 32 : 12}%`,
              opacity: index < bars ? 1 : 0.35,
            }}
          />
        ))}
      </span>
      <span aria-hidden="true" className="ad-level__letter">
        {levelLetters[level]}
      </span>
      {levelNames[level]}
    </span>
  )
}

/**
 * The comparison story renders the same fragments three times, so landmark
 * names must stay unique. Each column supplies a scope; single-direction
 * stories leave it empty and keep the plain Russian label.
 */
export const SceneScope = createContext('')

function useScopedLabel(label: string) {
  const scope = useContext(SceneScope)
  return scope ? `${label} — ${scope}` : label
}

/** Horizontal scroll needs keyboard access, otherwise wide tables trap content. */
function ScrollX({ label, children }: { label: string; children: React.ReactNode }) {
  const scopedLabel = useScopedLabel(label)
  return (
    <div aria-label={scopedLabel} className="ad-scroll-x" role="region" tabIndex={0}>
      {children}
    </div>
  )
}

function Section({
  title,
  note,
  index,
  children,
}: {
  title: string
  note?: string
  index: string
  children: React.ReactNode
}) {
  const headingId = useId()
  return (
    <section aria-labelledby={headingId} className="ad-section">
      <div className="ad-section__head">
        <span aria-hidden="true" className="ad-section__index">
          {index}
        </span>
        <h2 className="ad-section__title" id={headingId}>
          {title}
        </h2>
        {note ? <p className="ad-section__note">{note}</p> : null}
      </div>
      {children}
    </section>
  )
}

/* ------------------------------------------------------------ 1. brand */

export function BrandStrip({ direction }: { direction: DirectionId }) {
  const { Sign, Wordmark, Student, Family, Staff } = markSets[direction]
  return (
    <div className="ad-brandstrip">
      <div className="ad-brandstrip__group">
        <Wordmark size={24} />
      </div>
      <div className="ad-brandstrip__sizes">
        <Sign size={48} />
        <Sign size={24} />
        <Sign size={16} />
        <span className="ad-brandstrip__maskable">
          <Sign size={34} />
        </span>
      </div>
      <div className="ad-productmarks">
        <span className="ad-productmark">
          <Student size={20} /> Школьник
        </span>
        <span className="ad-productmark">
          <Family size={20} /> Семья
        </span>
        <span className="ad-productmark">
          <Staff size={20} /> Учитель
        </span>
      </div>
    </div>
  )
}

/* ---------------------------------------------------- 2. student mobile */

/** Bottom navigation uses Lucide: brand marks never double as interface icons. */
const navigation = [
  { label: 'Сейчас', Icon: House },
  { label: 'Задачи', Icon: BookOpenText },
  { label: 'Новости', Icon: Newspaper },
  { label: 'Прогресс', Icon: TrendingUp },
  { label: 'Профиль', Icon: UserRound },
] as const

export function StudentPhone({ direction }: { direction: DirectionId }) {
  const { Sign } = markSets[direction]
  const navigationLabel = useScopedLabel('Основная навигация')
  return (
    <div className="ad-phone">
      <div className="ad-phone__header">
        <Sign size={22} />
        <span className="ad-phone__title">
          <b>Занятие 21</b>
          <span>понедельник, 26 января</span>
        </span>
        <span style={{ marginLeft: 'auto' }}>
          <LevelChip level={1} />
        </span>
      </div>

      <div className="ad-phone__body">
        <div className="ad-stack ad-stack--tight">
          <p className="ad-label">Сейчас</p>
          <p style={{ margin: 0 }}>
            Условия опубликованы. Устная сдача сегодня до 19:00, письменные решения принимаем до
            воскресенья.
          </p>
          <div className="ad-deadline">
            <b>до воскресенья, 1 февраля, 13:00</b>
            <span>· осталось 5 дней</span>
          </div>
        </div>

        <ul
          className="ad-stack ad-stack--tight"
          style={{ listStyle: 'none', margin: 0, padding: 0 }}
        >
          {[
            {
              id: '21н.1',
              title: 'Разнообразные вагоны',
              kind: 'Тест',
              status: 'Верный ответ',
              tone: 'success',
            },
            {
              id: '21н.6',
              title: 'Расстановка ладей',
              kind: 'Письменная',
              status: 'На проверке',
              tone: 'info',
            },
            {
              id: '21н.8',
              title: 'Пример на вычитание',
              kind: 'Устная',
              status: 'Не начата',
              tone: 'neutral',
            },
          ].map((task) => (
            <li className="ad-panel" key={task.id}>
              <div className="ad-taskbar">
                <span className="ad-num ad-problem__index">{task.id}</span>
                <span className={`ad-status ad-status--${task.tone}`}>{task.status}</span>
              </div>
              <p style={{ margin: '0.25rem 0 0', fontWeight: 500 }}>{task.title}</p>
              <p
                className="ad-muted"
                style={{ margin: '0.125rem 0 0', fontSize: 'var(--ad-text-small)' }}
              >
                {task.kind}
              </p>
            </li>
          ))}
        </ul>
      </div>

      <nav aria-label={navigationLabel} className="ad-phone__nav">
        {navigation.map(({ label, Icon }, index) => (
          <button
            aria-current={index === 0 ? 'page' : undefined}
            className="ad-navitem"
            key={label}
            type="button"
          >
            <Icon aria-hidden="true" size={20} strokeWidth={1.75} />
            {label}
          </button>
        ))}
      </nav>
    </div>
  )
}

/* ------------------------------------------------- 3. reading document */

function Disclosure({ summary, children }: { summary: string; children: React.ReactNode }) {
  const [open, setOpen] = useState(false)
  const panelId = useId()
  return (
    <div className="ad-disclosure">
      <button
        aria-controls={panelId}
        aria-expanded={open}
        className="ad-disclosure__button"
        onClick={() => setOpen((value) => !value)}
        type="button"
      >
        {summary}
        <span aria-hidden="true" className="ad-disclosure__chevron">
          ›
        </span>
      </button>
      {open ? (
        <div className="ad-disclosure__panel" id={panelId}>
          {children}
        </div>
      ) : null}
    </div>
  )
}

export function Worksheet() {
  return (
    <article className="ad-worksheet">
      <header className="ad-worksheet__head">
        <h3 className="ad-worksheet__title">Листок 21н</h3>
        <p className="ad-worksheet__meta">
          Математический кружок, 179 школа, 5–7 класс · 26 января 2026
        </p>
      </header>

      <div className="ad-problem">
        <span className="ad-problem__index">21н.6</span>
        <h4 className="ad-problem__title">Расстановка ладей</h4>
        <div className="ad-problem__body">
          <p>
            Ладья бьёт по горизонтали или вертикали на любое количество клеток, но не бьёт сквозь
            другие фигуры.
          </p>
          <div className="ad-subitem">
            <span className="ad-subitem__marker">а)</span>
            <span>
              Расставьте на шахматной доске <M upright>8</M> разноцветных ладей, чтобы ни одна не
              била никакую другую.
            </span>
          </div>
          <div className="ad-subitem">
            <span className="ad-subitem__marker">б)</span>
            <span>
              Расставьте на шахматной доске <M upright>10</M> разноцветных ладей, чтобы каждая била
              ровно одну другую.
            </span>
          </div>
        </div>
        <div className="ad-figures">
          <figure className="ad-figure">
            <ChessRooksFigure />
            <figcaption className="ad-figcaption">
              Рис. 1. Пример расстановки к пункту а)
            </figcaption>
          </figure>
          <figure className="ad-figure">
            <SymmetryFigure />
            <figcaption className="ad-figcaption">Рис. 2. Заготовка к задаче 21н.7</figcaption>
          </figure>
        </div>
      </div>

      <div className="ad-problem">
        <span className="ad-problem__index">27х.1</span>
        <h4 className="ad-problem__title">Пять пятниц</h4>
        <div className="ad-problem__body">
          <p>
            Какое наибольшее количество месяцев, содержащих по пять пятниц, может быть в одном году?
          </p>
        </div>
        <Disclosure summary="Показать решение · опубликовано 1 февраля в 15:00">
          <p style={{ marginTop: 0 }}>
            <span className="ad-runin">Оценка.</span> В году либо <M upright>365</M>, либо{' '}
            <M upright>366</M> дней. Так как
          </p>
          <MathDisplay label="365 равно 7 умножить на 52 плюс 1" number="1">
            365 = 7 · 52 + 1,
          </MathDisplay>
          <p>
            то каждый год состоит из <M upright>52</M> полных недель и одного или двух
            дополнительных дней, поэтому в году не более <M upright>53</M> пятниц. В каждом месяце
            не меньше <M upright>28</M> дней, значит, не менее четырёх пятниц, и пять пятниц может
            быть не более чем в
          </p>
          <MathDisplay label="53 минус 4 умножить на 12 равно 5" number="2">
            53 − 4 · 12 = 5
          </MathDisplay>
          <p style={{ marginBottom: 0 }}>
            месяцах. <span className="ad-runin">Пример.</span> Если 1 января попадает на пятницу, то
            в году ровно <M upright>53</M> пятницы — так было в 2021 году и будет в 2027-м.
          </p>
        </Disclosure>
      </div>

      <div className="ad-problem">
        <span className="ad-problem__index">27х.3</span>
        <h4 className="ad-problem__title">Таблица умножения на языке болия</h4>
        <div className="ad-problem__body">
          <p>
            Даны некоторые строки из таблицы умножения на языке болия для чисел, произведения
            которых не превышают двадцати.
          </p>
          <ScrollX label="Таблица умножения на языке болия">
            <table className="ad-mathtable">
              <caption>Известные строки таблицы умножения</caption>
              <tbody>
                <tr>
                  <td>
                    <M>pe × nei = nei la nei</M>
                  </td>
                  <td>
                    <M>nei × hato = liomu la pe</M>
                  </td>
                  <td>
                    <M>hato × hato = nei la tano</M>
                  </td>
                </tr>
                <tr>
                  <td>
                    <M>pe × pe = nei</M>
                  </td>
                  <td>
                    <M>pe × tano = liomu</M>
                  </td>
                  <td>
                    <M>hato × ∗ = liomu la tano</M>
                  </td>
                </tr>
              </tbody>
            </table>
          </ScrollX>
          <p style={{ marginTop: '0.75rem' }}>
            Какое число скрыто в таблице под звёздочкой?{' '}
            <em>В ответе введите название числа на языке болия.</em>
          </p>
        </div>
      </div>
    </article>
  )
}

/* ------------------------------------------- 4. task status and actions */

export function TaskActions() {
  return (
    <div className="ad-panel ad-stack ad-stack--tight">
      <div className="ad-taskbar">
        <span className="ad-num ad-problem__index">21н.6</span>
        <LevelChip level={1} />
        <span className="ad-status ad-status--info">Отправлено, ждёт проверки</span>
        <span className="ad-status ad-status--neutral">Письменная</span>
      </div>
      <div className="ad-deadline">
        <b>Приём до воскресенья, 1 февраля, 13:00</b>
        <span>· осталось 5 дней · подсказки откроются в субботу в 12:00</span>
      </div>
      <p className="ad-muted" style={{ margin: 0, fontSize: 'var(--ad-text-small)' }}>
        Статистика по задаче появится после того, как закончится проверка всего занятия.
      </p>
      <div className="ad-actions">
        <button className="ad-btn ad-btn--primary" type="button">
          Отправить решение
        </button>
        <button className="ad-btn ad-btn--secondary" type="button">
          Сохранить черновик
        </button>
        <button className="ad-btn ad-btn--ghost" type="button">
          Задать вопрос
        </button>
        <button className="ad-btn ad-btn--danger" type="button">
          Удалить черновик
        </button>
      </div>
      <hr className="ad-rule" />
      <div className="ad-taskbar">
        <span className="ad-num ad-problem__index">20н.4</span>
        <span className="ad-status ad-status--success">Зачтено</span>
        <span className="ad-muted" style={{ fontSize: 'var(--ad-text-small)' }}>
          Проверка занятия завершена · решили 131 из 203
        </span>
      </div>
    </div>
  )
}

/* ------------------------------------------------ 5. written submission */

export function Composer() {
  const [synced, setSynced] = useState(false)
  const draftId = useId()
  return (
    <div className="ad-panel ad-stack ad-stack--tight">
      <div className="ad-field">
        <label className="ad-field__label" htmlFor={draftId}>
          Решение задачи 21н.6
        </label>
        <textarea
          className="ad-textarea"
          defaultValue={
            'а) Поставлю ладьи по диагонали: в каждой строке и в каждом столбце ровно одна ладья, значит, они не бьют друг друга.\nб) Разобью доску на пять пар соседних клеток…'
          }
          id={draftId}
        />
        <span className="ad-field__hint">
          Можно прикрепить до 10 фотографий. Порядок страниц сохраняется.
        </span>
      </div>

      <ul className="ad-photos" style={{ listStyle: 'none', margin: 0, padding: 0 }}>
        {[1, 2].map((page) => (
          <li className="ad-photo" key={page}>
            <NotebookPhoto variant={page as 1 | 2} />
            <span className="ad-photo__caption">
              Стр. {page}
              <button
                aria-label={`Переместить страницу ${page} назад`}
                className="ad-btn ad-btn--ghost ad-btn--sm"
                type="button"
              >
                ↑
              </button>
            </span>
          </li>
        ))}
      </ul>

      <p aria-live="polite" className={synced ? 'ad-syncline ad-syncline--synced' : 'ad-syncline'}>
        <span className="ad-syncline__text">
          {synced ? (
            <>
              <b>Отправлено. Сервер принял в 19:47</b>
              <span>Учтено как сдача от 19:42 — времени создания на вашем устройстве.</span>
            </>
          ) : (
            <>
              <b>Вы не в сети · 1 отправка в очереди</b>
              <span>Черновик сохранён в 19:42. Отправим сразу после подключения.</span>
            </>
          )}
        </span>
      </p>

      <div className="ad-actions">
        <button
          className="ad-btn ad-btn--secondary ad-btn--sm"
          onClick={() => setSynced((value) => !value)}
          type="button"
        >
          {synced ? 'Показать состояние «в очереди»' : 'Показать восстановление связи'}
        </button>
      </div>
    </div>
  )
}

/* -------------------------------------------------------------- 6. news */

export function NewsPost() {
  return (
    <div className="ad-panel ad-post">
      <p className="ad-post__meta">
        <span>Канал ВМШ 179</span>
        <span aria-hidden="true">·</span>
        <span className="ad-num">26 января, 16:30</span>
        <span aria-hidden="true">·</span>
        <span>переслано из «Условия»</span>
      </p>
      <div className="ad-post__body">
        <p>
          <strong>Условия 21-го занятия опубликованы.</strong> Начинающие решают листок{' '}
          <code>21н</code>, продолжающие — <code>21п</code>, эксперты — <code>21х</code>.
        </p>
        <p>
          Устная сдача идёт сегодня до 19:00, письменные решения принимаем до воскресенья, 13:00.
          Все условия также лежат{' '}
          <a href="#news-example" rel="noreferrer">
            на сайте кружка
          </a>
          .
        </p>
        <blockquote className="ad-quote">
          Если задача не выходит, начните «раскручивать» условие с конца и не стесняйтесь
          поперебирать варианты.
        </blockquote>
      </div>
      <ul className="ad-album" style={{ listStyle: 'none', margin: 0, padding: 0 }}>
        {[1, 2, 3, 4].map((variant) => (
          <li key={variant} style={{ display: 'contents' }}>
            <button
              aria-label={`Открыть фотографию ${variant} из 7`}
              className="ad-album__cell"
              type="button"
            >
              <AlbumThumb variant={variant as 1 | 2 | 3 | 4} />
              {variant === 4 ? (
                <span aria-hidden="true" className="ad-album__more">
                  +3
                </span>
              ) : null}
            </button>
          </li>
        ))}
      </ul>
      <p className="ad-tags">
        <span className="ad-tag">#условия</span>
        <span className="ad-tag">#занятие21</span>
      </p>
    </div>
  )
}

/* ------------------------------------------------------------- 7. staff */

const queue = [
  {
    id: '1042',
    student: 'Морозова Аня',
    task: '21н.6 а)',
    level: 1 as const,
    waiting: '00:12',
    owner: '—',
  },
  {
    id: '1041',
    student: 'Гринёв Пётр',
    task: '21н.6 б)',
    level: 1 as const,
    waiting: '00:31',
    owner: 'вы',
  },
  {
    id: '1038',
    student: 'Ким Даша',
    task: '21п.4',
    level: 2 as const,
    waiting: '01:04',
    owner: 'И. Соколов',
  },
  {
    id: '1035',
    student: 'Лебедев Слава',
    task: '21х.2',
    level: 3 as const,
    waiting: '02:20',
    owner: '—',
  },
]

export function StaffWorkspace() {
  return (
    <div className="ad-stack">
      <div className="ad-panel ad-panel--flush">
        <ScrollX label="Очередь письменной проверки">
          <table className="ad-table">
            <caption>
              Очередь письменной проверки · 43 работы, 7 взяты другими преподавателями
            </caption>
            <thead>
              <tr>
                <th scope="col">№</th>
                <th scope="col">Школьник</th>
                <th scope="col">Задача</th>
                <th scope="col">Уровень</th>
                <th scope="col">Ждёт</th>
                <th scope="col">Проверяет</th>
              </tr>
            </thead>
            <tbody>
              {queue.map((row, index) => (
                <tr data-selected={index === 1} key={row.id}>
                  <td className="ad-num">{row.id}</td>
                  <td>{row.student}</td>
                  <td className="ad-num">{row.task}</td>
                  <td>
                    <LevelChip level={row.level} />
                  </td>
                  <td className="ad-num">{row.waiting}</td>
                  <td>{row.owner}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </ScrollX>
      </div>

      <div className="ad-threepane">
        <div className="ad-pane">
          <h3 className="ad-pane__title">Очередь</h3>
          {queue.map((row, index) => (
            <button aria-current={index === 1} className="ad-queueitem" key={row.id} type="button">
              {row.student}
              <span className="ad-num">
                {row.task} · ждёт {row.waiting}
              </span>
            </button>
          ))}
        </div>

        <div className="ad-pane">
          <h3 className="ad-pane__title">Что прислал школьник</h3>
          <div className="ad-inline">
            <button className="ad-btn ad-btn--secondary ad-btn--sm" type="button">
              Перо
            </button>
            <button className="ad-btn ad-btn--ghost ad-btn--sm" type="button">
              Выделение
            </button>
            <button className="ad-btn ad-btn--ghost ad-btn--sm" type="button">
              Комментарий
            </button>
            <span className="ad-muted" style={{ fontSize: 'var(--ad-text-label)' }}>
              оригинал не изменяется
            </span>
          </div>
          <div className="ad-evidence">
            <NotebookPhoto variant={1} width={320} />
          </div>
        </div>

        <div className="ad-pane">
          <h3 className="ad-pane__title">Ответ и итог</h3>
          <p className="ad-muted" style={{ margin: 0, fontSize: 'var(--ad-text-small)' }}>
            Гринёв Пётр · Начинающие · вторая сдача этой задачи
          </p>
          <textarea
            aria-label="Комментарий школьнику"
            className="ad-textarea"
            defaultValue="Пункт а) полностью верный. В пункте б) объясните, почему пар ровно пять."
          />
          <div className="ad-actions">
            <button className="ad-btn ad-btn--primary ad-btn--sm" type="button">
              Зачесть
            </button>
            <button className="ad-btn ad-btn--secondary ad-btn--sm" type="button">
              Вернуть на доработку
            </button>
            <button className="ad-btn ad-btn--ghost ad-btn--sm" type="button">
              Отдать очереди
            </button>
          </div>
          <p className="ad-status ad-status--warning" style={{ alignSelf: 'flex-start' }}>
            Работа закреплена за вами до 20:15
          </p>
        </div>
      </div>
    </div>
  )
}

/* ----------------------------------------------------------- 8. signals */

export function Signals() {
  return (
    <div className="ad-stack ad-stack--tight">
      <div className="ad-signals">
        <p className="ad-signal ad-signal--success">
          <b>Зачтено</b>
          Решение принято 27 января в 21:08.
        </p>
        <p className="ad-signal ad-signal--warning">
          <b>Нужна доработка</b>
          Пересдача возможна до закрытия приёма.
        </p>
        <p className="ad-signal ad-signal--danger">
          <b>Отправка не удалась</b>
          Файл больше 20 МБ. Черновик сохранён.
        </p>
        <p className="ad-signal ad-signal--info">
          <b>На проверке</b>
          Обычно занимает около суток.
        </p>
      </div>
      <div className="ad-signals">
        <p className="ad-signal ad-signal--level-1">
          <b>Начинающие</b>
          Уровень, а не оценка.
        </p>
        <p className="ad-signal ad-signal--level-2">
          <b>Продолжающие</b>
          Уровень, а не оценка.
        </p>
        <p className="ad-signal ad-signal--level-3">
          <b>Эксперты</b>
          Уровень, а не оценка.
        </p>
        <p className="ad-signal ad-signal--level-0">
          <b>Тестирование</b>
          Служебная группа.
        </p>
      </div>
      <div className="ad-inline">
        <button className="ad-btn ad-btn--secondary ad-btn--sm ad-focusdemo" type="button">
          Кольцо фокуса
        </button>
        <span className="ad-muted" style={{ fontSize: 'var(--ad-text-small)' }}>
          Так выглядит focus-visible; нажмите Tab, чтобы проверить его на остальных элементах.
        </span>
      </div>
    </div>
  )
}

/* -------------------------------------------------------- 9. typography */

export function TypeSpecimen({ direction }: { direction: DirectionId }) {
  const meta = directions[direction]
  return (
    <div className="ad-specimen">
      <p className="ad-specimen__display">Вечерняя математическая школа</p>
      <div className="ad-specimen__row">
        <span className="ad-specimen__caption">Чтение · {meta.reading}</span>
        <span className="ad-problem__body" style={{ flex: '1 1 20rem' }}>
          Ёжик съел четверть, а потом ещё <M upright>3</M> × <M upright>5</M> ягод; в
          последовательности встречаются числа <M upright>−7</M> и <M upright>179</M>, а
          «взаимно-однозначное соответствие» пишется через дефис.
        </span>
      </div>
      <div className="ad-specimen__row">
        <span className="ad-specimen__caption">Интерфейс · {meta.ui}</span>
        <span>Сдать решение · Подсказки откроются в субботу · Черновик сохранён</span>
      </div>
      <div className="ad-specimen__row">
        <span className="ad-specimen__caption">Цифры таблиц</span>
        <span className="ad-num">0123456789 · 16:30 · 131/203 · 21н.6 а)</span>
      </div>
    </div>
  )
}

/* --------------------------------------------------------------- scene */

export function ArtDirectionScene({
  direction,
  density = 'student',
}: {
  direction: DirectionId
  density?: Density
}) {
  const meta = directions[direction]
  return (
    <div className="ad-root" data-ad={direction} data-density={density}>
      <div className="ad-page">
        <header>
          <h1 style={{ margin: 0, fontSize: '1.375rem', fontWeight: 600 }}>{meta.name}</h1>
          <p className="ad-muted" style={{ margin: '0.25rem 0 0', maxWidth: '46rem' }}>
            {meta.idea}
          </p>
        </header>

        <Section index="01" title="Знак, логотип и три продуктовые иконки">
          <BrandStrip direction={direction} />
        </Section>

        <Section index="02" title="Школьник на телефоне" note="390 × 844">
          <StudentPhone direction={direction} />
        </Section>

        <Section index="03" title="Длинное условие: формула, подпункты, рисунок">
          <Worksheet />
        </Section>

        <Section index="04" title="Статус задачи, дедлайн и действия">
          <TaskActions />
        </Section>

        <Section index="05" title="Письменная сдача, фотографии и очередь отправки">
          <Composer />
        </Section>

        <Section index="06" title="Новость из Telegram с альбомом">
          <NewsPost />
        </Section>

        <Section index="07" title="Очередь и трёхзонная проверка" note="плотность Staff">
          <div className="ad-root" data-ad={direction} data-density="staff">
            <StaffWorkspace />
          </div>
        </Section>

        <Section index="08" title="Значения статусов, уровней и фокуса рядом">
          <Signals />
        </Section>

        <Section index="09" title="Типографика и кириллица">
          <TypeSpecimen direction={direction} />
        </Section>
      </div>
    </div>
  )
}
