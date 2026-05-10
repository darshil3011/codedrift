import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { IndexHealth } from './sections/IndexHealth'
import { ToolUsage } from './sections/ToolUsage'
import { ActivityTimeline } from './sections/ActivityTimeline'
import { IndexHistory } from './sections/IndexHistory'
import { TokenSavings } from './sections/TokenSavings'
import { SymbolHeatmap } from './sections/SymbolHeatmap'
import { MemoryHitRate } from './sections/MemoryHitRate'
import { ResponseSize } from './sections/ResponseSize'

const queryClient = new QueryClient()

function Dashboard() {
  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200 px-6 py-4 flex items-center gap-3">
        <span className="text-xl">🌊</span>
        <h1 className="text-xl font-bold text-gray-900">CodeDrift Analytics</h1>
      </header>
      <main className="max-w-6xl mx-auto px-6 py-8 flex flex-col gap-10">
        <IndexHealth />
        <div className="border-t border-gray-100" />
        <ToolUsage />
        <div className="border-t border-gray-100" />
        <ActivityTimeline />
        <div className="border-t border-gray-100" />
        <TokenSavings />
        <div className="border-t border-gray-100" />
        <SymbolHeatmap />
        <div className="border-t border-gray-100" />
        <MemoryHitRate />
        <div className="border-t border-gray-100" />
        <ResponseSize />
        <div className="border-t border-gray-100" />
        <IndexHistory />
      </main>
    </div>
  )
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <Dashboard />
    </QueryClientProvider>
  )
}
