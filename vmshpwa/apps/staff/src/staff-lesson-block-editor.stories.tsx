import type { Meta, StoryObj } from '@storybook/react-vite'
import { StaffLessonBlockEditor } from './staff-lesson-block-editor'
const noop = async () => {}
const meta = {
  title: 'Staff/Lesson block editor',
  component: StaffLessonBlockEditor,
  args: {
    block: null,
    businessTimezone: 'Europe/Moscow',
    groupLessonId: 'lesson-demo',
    position: 'before',
    title: 'Блок перед задачами',
    refetch: noop,
    client: {
      get: () => Promise.reject(new Error('Unused')),
      save: noop,
      publish: noop,
      hide: noop,
      cancel: noop,
      uploadImage: () => Promise.reject(new Error('Story does not upload')),
    },
  },
} satisfies Meta<typeof StaffLessonBlockEditor>
export default meta
export const Empty: StoryObj<typeof meta> = {}
