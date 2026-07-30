import { Tabs, TabsList, TabsTrigger } from '@vmsh/ui'

export type UsersSection = 'students' | 'teachers'

export function UsersSectionTabs({
  section,
  showTeachers,
  onChange,
}: {
  section: UsersSection
  showTeachers: boolean
  onChange: (section: UsersSection) => void
}) {
  return (
    <Tabs onValueChange={(value) => onChange(value as UsersSection)} value={section}>
      <TabsList aria-label="Раздел участников" variant="line">
        <TabsTrigger value="students">Школьники</TabsTrigger>
        {showTeachers ? <TabsTrigger value="teachers">Преподаватели</TabsTrigger> : null}
      </TabsList>
    </Tabs>
  )
}
