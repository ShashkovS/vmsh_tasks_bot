import type { CourseView, GroupView } from './types'

export const mathCourse: CourseView = {
  id: 'math-5-7',
  code: 'math-5-7',
  name: 'Математика 5–7',
  subjectCode: 'Математика',
  accentIndex: 1,
}

export const physicsCourse: CourseView = {
  id: 'physics-6-7',
  code: 'physics-6-7',
  name: 'Физика 6–7',
  subjectCode: 'Физика',
  accentIndex: 3,
}

export const mathGroups: GroupView[] = [
  { id: 'math-beginner', courseId: mathCourse.id, code: 'н', name: 'Начинающие', colorIndex: 1 },
  {
    id: 'math-continuing',
    courseId: mathCourse.id,
    code: 'п',
    name: 'Продолжающие',
    colorIndex: 2,
  },
  { id: 'math-expert', courseId: mathCourse.id, code: 'э', name: 'Эксперты', colorIndex: 3 },
]

export const physicsGroups: GroupView[] = [
  {
    id: 'physics-intro',
    courseId: physicsCourse.id,
    code: 'зн',
    name: 'Знакомство',
    colorIndex: 1,
  },
  { id: 'physics-lab', courseId: physicsCourse.id, code: 'оп', name: 'Опыты', colorIndex: 4 },
]
