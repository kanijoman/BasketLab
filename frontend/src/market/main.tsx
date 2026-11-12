/** Entry of BasketLab Talent (#877): the same providers, theme and design tokens as Analytics (`src/main.tsx`), another app. */
import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MotionConfig } from 'framer-motion'
import MarketApp from './MarketApp'
import { applyStoredTheme } from '@/lib/theme'
import { consumeInviteFromUrl } from '@/webdata/invite'
import { DataNotAvailable } from '@/datasource/resolve'
import '@design/tokens.css'
import '@fontsource-variable/inter'
import '@fontsource-variable/space-grotesk'
import '@fontsource-variable/jetbrains-mono'
import '@/index.css'

applyStoredTheme()
consumeInviteFromUrl()

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: (failures, error) => !(error instanceof DataNotAvailable) && failures < 1,
      staleTime: 5 * 60 * 1000,
    },
  },
})

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <MotionConfig reducedMotion="user">
        <BrowserRouter>
          <MarketApp />
        </BrowserRouter>
      </MotionConfig>
    </QueryClientProvider>
  </React.StrictMode>,
)
