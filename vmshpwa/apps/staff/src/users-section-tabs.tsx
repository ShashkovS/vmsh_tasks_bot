import { t } from '@lingui/core/macro'
import { Trans } from '@lingui/react/macro'
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
      <TabsList aria-label={t`Раздел участников`} variant="line">
        <TabsTrigger value="students">
          <Trans>Школьники</Trans>
        </TabsTrigger>
        {showTeachers ? (
          <TabsTrigger value="teachers">
            <Trans>Преподаватели</Trans>
          </TabsTrigger>
        ) : null}
        {showImports ? (
          <TabsTrigger value="imports">
            <Trans>Добавление</Trans>
          </TabsTrigger>
        ) : null}
      </TabsList>
    </Tabs>
  )
}
