'use client'

import { Drawer as DrawerPrimitive } from '@base-ui/react/drawer'
import { XIcon } from 'lucide-react'
import * as React from 'react'

import { Button } from '@vmsh/ui/components/button'
import { cn } from '@vmsh/ui/lib/utils'

type DrawerSide = 'top' | 'right' | 'bottom' | 'left'

const DrawerSideContext = React.createContext<DrawerSide>('right')

function Drawer({ side = 'right', ...props }: DrawerPrimitive.Root.Props & { side?: DrawerSide }) {
  const swipeDirection = {
    top: 'up',
    right: 'right',
    bottom: 'down',
    left: 'left',
  } as const

  return (
    <DrawerSideContext value={side}>
      <DrawerPrimitive.Root swipeDirection={swipeDirection[side]} {...props} />
    </DrawerSideContext>
  )
}

function DrawerTrigger(props: DrawerPrimitive.Trigger.Props) {
  return <DrawerPrimitive.Trigger data-slot="drawer-trigger" {...props} />
}

function DrawerClose(props: DrawerPrimitive.Close.Props) {
  return <DrawerPrimitive.Close data-slot="drawer-close" {...props} />
}

function DrawerOverlay({ className, ...props }: DrawerPrimitive.Backdrop.Props) {
  return (
    <DrawerPrimitive.Backdrop
      data-slot="drawer-overlay"
      className={cn(
        'fixed inset-0 z-50 bg-foreground/10 transition-opacity duration-150 data-ending-style:opacity-0 data-starting-style:opacity-0 supports-backdrop-filter:backdrop-blur-xs',
        className,
      )}
      {...props}
    />
  )
}

function DrawerContent({
  className,
  children,
  showCloseButton = true,
  ...props
}: DrawerPrimitive.Popup.Props & { showCloseButton?: boolean }) {
  const side = React.use(DrawerSideContext)

  return (
    <DrawerPrimitive.Portal>
      <DrawerOverlay />
      <DrawerPrimitive.Viewport
        data-slot="drawer-viewport"
        data-side={side}
        className="pointer-events-none fixed inset-0 z-50 flex data-[side=bottom]:items-end data-[side=left]:justify-start data-[side=right]:justify-end data-[side=top]:items-start"
      >
        <DrawerPrimitive.Popup
          data-slot="drawer-content"
          data-side={side}
          className={cn(
            'pointer-events-auto relative flex max-h-svh flex-col border bg-popover text-sm text-popover-foreground shadow-lg transition-transform duration-200 ease-out data-ending-style:opacity-0 data-starting-style:opacity-0',
            'data-[side=bottom]:max-h-[85svh] data-[side=bottom]:w-full data-[side=bottom]:rounded-t-xl data-[side=bottom]:border-t data-[side=bottom]:data-ending-style:translate-y-full data-[side=bottom]:data-starting-style:translate-y-full',
            'data-[side=top]:max-h-[85svh] data-[side=top]:w-full data-[side=top]:rounded-b-xl data-[side=top]:border-b data-[side=top]:data-ending-style:-translate-y-full data-[side=top]:data-starting-style:-translate-y-full',
            'data-[side=left]:h-full data-[side=left]:w-[min(24rem,90vw)] data-[side=left]:border-r data-[side=left]:data-ending-style:-translate-x-full data-[side=left]:data-starting-style:-translate-x-full',
            'data-[side=right]:h-full data-[side=right]:w-[min(24rem,90vw)] data-[side=right]:border-l data-[side=right]:data-ending-style:translate-x-full data-[side=right]:data-starting-style:translate-x-full',
            className,
          )}
          {...props}
        >
          <DrawerPrimitive.Content className="flex min-h-0 flex-1 flex-col">
            {children}
          </DrawerPrimitive.Content>
          {showCloseButton ? (
            <DrawerPrimitive.Close
              data-slot="drawer-close"
              render={<Button variant="ghost" className="absolute top-3 right-3" size="icon-sm" />}
            >
              <XIcon aria-hidden="true" />
              <span className="sr-only">Закрыть панель</span>
            </DrawerPrimitive.Close>
          ) : null}
        </DrawerPrimitive.Popup>
      </DrawerPrimitive.Viewport>
    </DrawerPrimitive.Portal>
  )
}

function DrawerHeader({ className, ...props }: React.ComponentProps<'div'>) {
  return (
    <div
      data-slot="drawer-header"
      className={cn('flex flex-col gap-1 p-4', className)}
      {...props}
    />
  )
}

function DrawerFooter({ className, ...props }: React.ComponentProps<'div'>) {
  return (
    <div
      data-slot="drawer-footer"
      className={cn('mt-auto flex flex-col gap-2 p-4', className)}
      {...props}
    />
  )
}

function DrawerTitle({ className, ...props }: DrawerPrimitive.Title.Props) {
  return (
    <DrawerPrimitive.Title
      data-slot="drawer-title"
      className={cn('text-base font-medium', className)}
      {...props}
    />
  )
}

function DrawerDescription({ className, ...props }: DrawerPrimitive.Description.Props) {
  return (
    <DrawerPrimitive.Description
      data-slot="drawer-description"
      className={cn('text-sm text-muted-foreground', className)}
      {...props}
    />
  )
}

export {
  Drawer,
  DrawerTrigger,
  DrawerClose,
  DrawerContent,
  DrawerHeader,
  DrawerFooter,
  DrawerTitle,
  DrawerDescription,
}
