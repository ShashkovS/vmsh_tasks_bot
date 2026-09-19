import { Tabs, TabsList, TabsTrigger } from '@vmsh/ui'

export type UsersSection = 'students' | 'teachers' | 'imports'

export function UsersSectionTabs({
  section,
  showTeachers,
  showImports = false,
  onChange,
}: {
  section: UsersSection
  showTeachers: boolean
  showImports?: boolean
  onChange: (section: UsersSection) => void
}) {
  return (
    <Tabs onValueChange={(value) => onChange(value as UsersSection)} value={section}>
      <TabsList aria-label="Раздел участников" variant="line">
        <TabsTrigger value="students">Школьники</TabsTrigger>
        {showTeachers ? <TabsTrigger value="teachers">Преподаватели</TabsTrigger> : null}
        {showImports ? <TabsTrigger value="imports">Добавление</TabsTrigger> : null}
      </TabsList>
    </Tabs>
  )
}
