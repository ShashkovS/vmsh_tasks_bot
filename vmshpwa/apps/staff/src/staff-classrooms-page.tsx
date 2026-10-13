import { t } from '@lingui/core/macro'
import { Trans } from '@lingui/react/macro'
import type { ReactNode } from 'react'
import { PageLayout } from '@vmsh/app-shell'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@vmsh/ui'

export type ClassroomPageTab = 'catalog' | 'groups' | 'students'

// Production route shell for P5 classrooms. The illustrative composition in
// pages.tsx remains a Storybook-only fixture; this component owns live chrome.
export function StaffClassroomsPage({
  tab,
  onTabChange,
  event,
  catalog,
  layout,
  students,
}: {
  tab: ClassroomPageTab
  onTabChange: (tab: ClassroomPageTab) => void
  event: ReactNode
  catalog: ReactNode
  layout: ReactNode
  students: ReactNode
}) {
  return (
    <PageLayout
      description={t`Каталог, схема по группам и версионируемый план для выбранного очного события.`}
      title={t`Аудитории`}
      width="wide"
    >
      <div className="space-y-6">
        {event}
        <Tabs onValueChange={(value) => onTabChange(value as ClassroomPageTab)} value={tab}>
          <TabsList>
            <TabsTrigger value="catalog">
              <Trans>Каталог</Trans>
            </TabsTrigger>
            <TabsTrigger value="groups">
              <Trans>По группам</Trans>
            </TabsTrigger>
            <TabsTrigger value="students">
              <Trans>Школьники</Trans>
            </TabsTrigger>
          </TabsList>
          <TabsContent value="catalog">{catalog}</TabsContent>
          <TabsContent value="groups">{layout}</TabsContent>
          <TabsContent value="students">{students}</TabsContent>
        </Tabs>
      </div>
    </PageLayout>
  )
}
