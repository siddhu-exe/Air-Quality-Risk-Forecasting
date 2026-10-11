import { Logo } from './Logo'
import { MobileNav } from './MobileNav'
import { SectionNav } from './SectionNav'
import { StatusCluster } from './StatusCluster'

export function SiteHeader() {
  return (
    <header className="flex flex-wrap items-center gap-x-8 gap-y-3 border-b border-line bg-surface px-5 py-3 md:px-10 md:py-3.5">
      <Logo />
      <SectionNav className="hidden md:flex" />
      <StatusCluster className="ml-auto hidden md:flex" />
      <MobileNav />
    </header>
  )
}
