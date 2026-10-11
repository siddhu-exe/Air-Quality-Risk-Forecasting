import { QueryClientProvider } from '@tanstack/react-query'
import { useState, type ReactNode } from 'react'
import { createQueryClient } from './queryClient'

export function Providers({ children }: { children: ReactNode }) {
  // Created once per mount; a module-level client would leak between tests.
  const [client] = useState(createQueryClient)
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>
}
