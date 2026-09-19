'use client'

import { Toast as ToastPrimitive } from '@base-ui/react/toast'
import {
  CheckCircle2Icon,
  CircleAlertIcon,
  InfoIcon,
  LoaderCircleIcon,
  TriangleAlertIcon,
  XIcon,
} from 'lucide-react'
import type { ReactNode } from 'react'

import { cn } from '@vmsh/ui/lib/utils'

type ToastKind = 'success' | 'info' | 'warning' | 'error' | 'loading'

export const toastManager = ToastPrimitive.createToastManager()

function addToast(kind: ToastKind, title: ReactNode, description?: ReactNode) {
  return toastManager.add({
    title,
    type: kind,
    ...(description === undefined ? {} : { description }),
    priority: kind === 'error' ? 'high' : 'low',
    timeout: kind === 'loading' ? 0 : undefined,
  })
}

export const toast = {
  success: (title: ReactNode, description?: ReactNode) => addToast('success', title, description),
  info: (title: ReactNode, description?: ReactNode) => addToast('info', title, description),
  warning: (title: ReactNode, description?: ReactNode) => addToast('warning', title, description),
  error: (title: ReactNode, description?: ReactNode) => addToast('error', title, description),
  loading: (title: ReactNode, description?: ReactNode) => addToast('loading', title, description),
  dismiss: (id?: string) => toastManager.close(id),
  update: toastManager.update,
  promise: toastManager.promise,
}

function ToastIcon({ type }: { type?: string }) {
  const className = 'mt-0.5 size-4 shrink-0'
  switch (type) {
    case 'success':
      return (
        <CheckCircle2Icon className={cn(className, 'text-status-success')} aria-hidden="true" />
      )
    case 'warning':
      return (
        <TriangleAlertIcon className={cn(className, 'text-status-warning')} aria-hidden="true" />
      )
    case 'error':
      return <CircleAlertIcon className={cn(className, 'text-destructive')} aria-hidden="true" />
    case 'loading':
      return (
        <LoaderCircleIcon
          className={cn(className, 'animate-spin text-primary')}
          aria-hidden="true"
        />
      )
    default:
      return <InfoIcon className={cn(className, 'text-status-info')} aria-hidden="true" />
  }
}

function ToastList() {
  const { toasts } = ToastPrimitive.useToastManager()

  return toasts.map((item) => (
    <ToastPrimitive.Root
      key={item.id}
      toast={item}
      className="pointer-events-auto relative flex w-full origin-bottom gap-3 rounded-lg border bg-popover p-4 pr-10 text-popover-foreground shadow-lg transition-[transform,opacity] duration-150 data-ending-style:translate-y-2 data-ending-style:opacity-0 data-limited:hidden data-starting-style:translate-y-2 data-starting-style:opacity-0"
    >
      <ToastIcon {...(item.type === undefined ? {} : { type: item.type })} />
      <ToastPrimitive.Content className="min-w-0 flex-1">
        <ToastPrimitive.Title className="text-sm font-medium" />
        {item.description ? (
          <ToastPrimitive.Description className="mt-1 text-sm leading-5 text-muted-foreground" />
        ) : null}
        {item.actionProps ? (
          <ToastPrimitive.Action
            {...item.actionProps}
            className={cn(
              'mt-3 min-h-8 rounded-md border px-3 text-sm font-medium hover:bg-muted focus-visible:ring-3 focus-visible:ring-ring/50',
              item.actionProps.className,
            )}
          />
        ) : null}
      </ToastPrimitive.Content>
      <ToastPrimitive.Close
        className="absolute top-2.5 right-2.5 inline-flex size-8 items-center justify-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground focus-visible:ring-3 focus-visible:ring-ring/50"
        aria-label="Закрыть уведомление"
      >
        <XIcon className="size-4" aria-hidden="true" />
      </ToastPrimitive.Close>
    </ToastPrimitive.Root>
  ))
}

export interface ToasterProps {
  limit?: number
  timeout?: number
}

export function Toaster({ limit = 3, timeout = 5000 }: ToasterProps) {
  return (
    <ToastPrimitive.Provider toastManager={toastManager} limit={limit} timeout={timeout}>
      <ToastPrimitive.Portal>
        <ToastPrimitive.Viewport className="pointer-events-none fixed right-4 bottom-4 z-50 flex w-[min(24rem,calc(100vw-2rem))] flex-col-reverse gap-2 outline-none">
          <ToastList />
        </ToastPrimitive.Viewport>
      </ToastPrimitive.Portal>
    </ToastPrimitive.Provider>
  )
}
