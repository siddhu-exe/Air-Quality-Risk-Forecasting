export interface NavItem {
  to: string
  label: string
  /** Match only the exact path (the Overview route is "/"). */
  end?: boolean
}

/** The four sections of the app, in design order. */
export const NAV_ITEMS: readonly NavItem[] = [
  { to: '/', label: 'Overview', end: true },
  { to: '/stations', label: 'Stations' },
  { to: '/operations', label: 'Operations' },
  { to: '/model-health', label: 'Model health' },
]
