import { t } from '@lingui/core/macro'
import { Trans } from '@lingui/react/macro'
import { Tabs, TabsList, TabsTrigger } from '@vmsh/ui'

export type UsersSection = 'students' | 'teachers' | 'imports' | 'work'

export function UsersSectionTabs({
  section,
  showTeachers,
  showImports = false,
  showWork = showImports,
  onChange,
}: {
  section: UsersSection
  showTeachers: boolean
  showImports?: boolean
  showWork?: boolean
  onChange: (section: UsersSection) => void
}) {
  return (
    <div className="max-w-full overflow-x-auto pb-2">
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
          {showWork ? (
            <TabsTrigger value="work">
              <Trans>Учёт работы</Trans>
            </TabsTrigger>
          ) : null}
        </TabsList>
      </Tabs>
    </div>
  )
}
