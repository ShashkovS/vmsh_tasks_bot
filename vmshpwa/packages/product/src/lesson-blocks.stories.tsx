import type { Meta, StoryObj } from '@storybook/react-vite'
import { LessonBlocksLayout } from './lesson-blocks'
import { parseLessonRichMarkdown } from './lesson-rich-markdown'

const meta = {
  title: 'Product/Lesson blocks',
  component: LessonBlocksLayout,
  parameters: { layout: 'padded' },
} satisfies Meta<typeof LessonBlocksLayout>
export default meta
type Story = StoryObj<typeof meta>
export const Videos: Story = {
  args: {
    idPrefix: 'story',
    before: parseLessonRichMarkdown('## Перед занятием\n\nПовторим формулу $a^2+b^2=c^2$.'),
    after: parseLessonRichMarkdown(
      '## Запись онлайн-разбора\n\nРазбор задач второго занятия для начинающих.\n\n::video[YouTube](https://youtu.be/4ke2IJirSds)\n\n::video[VK Видео](https://vkvideo.ru/video_ext.php?oid=-241691838&id=456239017&hd=2)\n',
    ),
    children: <div className="rounded-xl border border-border bg-surface p-8">Задачи занятия</div>,
  },
}
