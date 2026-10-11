import { NavLink } from 'react-router-dom'
import { cn } from '@/lib/cn'
import { NAV_ITEMS } from './nav'

interface SectionNavProps {
  /** `row` is the header pill row, `column` the full-width list in the drawer. */
  layout?: 'row' | 'column'
  /** Called after a link is chosen (closes the drawer). */
  onNavigate?: () => void
  className?: string
}

export function SectionNav({ layout = 'row', onNavigate, className }: SectionNavProps) {
  return (
    <nav
      aria-label="Sections"
      className={cn('flex gap-1', layout === 'row' ? 'flex-wrap' : 'flex-col', className)}
    >
      {NAV_ITEMS.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.end}
          {...(onNavigate ? { onClick: onNavigate } : {})}
          className={({ isActive }) =>
            cn(
              'inline-flex items-center rounded-full px-3.5 no-underline transition-colors duration-150',
              layout === 'row' ? 'min-h-10' : 'min-h-target',
              isActive
                ? 'bg-ink font-medium text-white hover:text-white'
                : 'text-ink-2 hover:bg-wash hover:text-ink',
            )
          }
        >
          {item.label}
        </NavLink>
      ))}
    </nav>
  )
}
