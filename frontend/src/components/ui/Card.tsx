import type { ComponentPropsWithoutRef, ElementType } from 'react'
import { cn } from '@/lib/cn'

type CardProps<T extends ElementType> = {
  /** Element to render; use `section` or `aside` when the card is a landmark-worthy region. */
  as?: T
} & Omit<ComponentPropsWithoutRef<T>, 'as'>

/**
 * White 16px-radius surface with a hairline border. Padding is deliberately
 * left to callers: the design uses a different inset for almost every card.
 */
export function Card<T extends ElementType = 'div'>({ as, className, ...props }: CardProps<T>) {
  const Component: ElementType = as ?? 'div'
  return <Component className={cn('rounded-2xl border border-line bg-surface', className)} {...props} />
}
