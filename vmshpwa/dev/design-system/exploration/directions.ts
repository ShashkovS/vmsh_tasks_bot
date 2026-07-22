/** Phase 1 exploration only — none of these is an accepted direction. */
export type DirectionId = 'a' | 'b' | 'c'

export interface Direction {
  id: DirectionId
  /** Short working name used in Storybook and in the gate discussion. */
  name: string
  /** One sentence: the central visual idea. */
  idea: string
  reading: string
  ui: string
  /** What a reviewer should look at first. */
  focus: string
}

export const directions: Record<DirectionId, Direction> = {
  a: {
    id: 'a',
    name: 'A · «Листок»',
    idea: 'Интерфейс — поля вокруг напечатанного листка: тёплая бумага для чтения внутри холодной тихой оболочки.',
    reading: 'Literata',
    ui: 'Inter',
    focus: 'Линейки вместо карточек, номер задачи вынесен на поле, нулевая тень.',
  },
  b: {
    id: 'b',
    name: 'B · «Мастерская»',
    idea: 'Один нейтральный рабочий холст и точные панели инструментов; бумага не имитируется.',
    reading: 'Source Serif 4',
    ui: 'IBM Plex Sans',
    focus: 'Панели с мягким радиусом, зебра в таблицах, самый технический Staff.',
  },
  c: {
    id: 'c',
    name: 'C · «Архив»',
    idea: 'Всё каталогизировано: тёплая бумажная материальность, печатные индексы и каталожная рейка.',
    reading: 'PT Serif',
    ui: 'Golos Text',
    focus: 'Почти прямые углы, двойные линейки, индекс уровня буквой, никакой тени.',
  },
}

export const directionOrder: DirectionId[] = ['a', 'b', 'c']
