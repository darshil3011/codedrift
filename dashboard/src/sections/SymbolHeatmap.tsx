import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import { useSymbolHeatmap } from '../hooks/useQueries'
import { LoadingSpinner } from '../components/LoadingSpinner'
import { ErrorBanner } from '../components/ErrorBanner'

const KIND_COLOR: Record<string, string> = {
  function: '#6366f1',
  class: '#8b5cf6',
  method: '#0d9488',
}
const DEFAULT_COLOR = '#94a3b8'

export function SymbolHeatmap() {
  const { data, isLoading, error } = useSymbolHeatmap()

  if (isLoading) return <LoadingSpinner />
  if (error || !data) return <ErrorBanner message="Failed to load symbol heatmap" />
  if (!data.length) return <p className="text-gray-400 text-sm py-6">No resolve calls recorded yet.</p>

  const chart = [...data].reverse()

  return (
    <section>
      <h2 className="text-lg font-semibold text-gray-800 mb-1">Symbol Heatmap</h2>
      <p className="text-xs text-gray-400 mb-3">Top 20 most-resolved symbols</p>
      <div className="flex gap-4 mb-3 text-xs text-gray-500">
        {Object.entries(KIND_COLOR).map(([k, c]) => (
          <span key={k} className="flex items-center gap-1"><span className="inline-block w-3 h-3 rounded-sm" style={{ background: c }} />{k}</span>
        ))}
      </div>
      <ResponsiveContainer width="100%" height={Math.max(220, chart.length * 28)}>
        <BarChart layout="vertical" data={chart} margin={{ top: 4, right: 32, left: 80, bottom: 4 }}>
          <XAxis type="number" tick={{ fontSize: 11 }} />
          <YAxis type="category" dataKey="symbol" tick={{ fontSize: 11 }} width={80} />
          <Tooltip formatter={(v: number) => [v, 'Calls']} labelFormatter={(l: string) => `Symbol: ${l}`} />
          <Bar dataKey="call_count" name="Calls" radius={[0, 4, 4, 0]}>
            {chart.map((entry, i) => (
              <Cell key={i} fill={KIND_COLOR[entry.kind ?? ''] ?? DEFAULT_COLOR} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </section>
  )
}
