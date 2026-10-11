import * as Dialog from '@radix-ui/react-dialog'
import { useState } from 'react'
import { SectionNav } from './SectionNav'
import { StatusCluster } from './StatusCluster'

/** Hamburger and slide-over drawer for phones. Focus is trapped and Escape closes it. */
export function MobileNav() {
  const [open, setOpen] = useState(false)

  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <Dialog.Trigger asChild>
        <button
          type="button"
          aria-label="Open menu"
          className="-mr-2 ml-auto flex h-11 w-11 items-center justify-center md:hidden"
        >
          <svg width="20" height="20" viewBox="0 0 20 20" aria-hidden="true">
            <path d="M3 6h14M3 10h14M3 14h14" className="stroke-ink" strokeWidth="1.6" strokeLinecap="round" />
          </svg>
        </button>
      </Dialog.Trigger>

      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 animate-fade-in bg-ink/50" />
        <Dialog.Content className="fixed right-0 top-0 z-50 flex h-dvh w-[min(320px,85vw)] animate-slide-in-right flex-col gap-6 border-l border-line bg-surface p-5">
          <div className="flex items-center justify-between">
            <Dialog.Title className="text-17 font-semibold">Menu</Dialog.Title>
            <Dialog.Close asChild>
              <button type="button" aria-label="Close menu" className="-mr-2 flex h-11 w-11 items-center justify-center">
                <svg width="20" height="20" viewBox="0 0 20 20" aria-hidden="true">
                  <path d="M5 5l10 10M15 5L5 15" className="stroke-ink" strokeWidth="1.6" strokeLinecap="round" />
                </svg>
              </button>
            </Dialog.Close>
          </div>
          <Dialog.Description className="sr-only">Choose a section of Delhi Air Forecast.</Dialog.Description>
          <SectionNav layout="column" onNavigate={() => setOpen(false)} />
          <StatusCluster className="mt-auto flex-col items-start" />
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
