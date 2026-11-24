import type { Meta, StoryObj } from '@storybook/react-vite'
import { fn } from 'storybook/test'

import { CourseCatalogEditor } from './course-catalog-editors'

// docs/metadata-generation.md and 05-pages-and-flows.md: course settings dialog.
const meta = {
  title: 'Pages/Staff/Course settings',
  component: CourseCatalogEditor,
  args: {
    course: null,
    open: true,
    saving: false,
    storageKey: 'storybook:course-settings',
    onOpenChange: fn(),
    onSave: fn(),
  },
} satisfies Meta<typeof CourseCatalogEditor>

export default meta
type Story = StoryObj<typeof meta>

export const NewCourse: Story = {}
export const English: Story = { globals: { locale: 'en' } }
export const Dark: Story = { globals: { theme: 'dark' } }
export const Saving: Story = { args: { saving: true } }
