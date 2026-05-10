import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from 'recharts'
import { useMemoryHitRate } from '../hooks/useQueries'
import { LoadingSpinner } from '../components/LoadingSpinner'
import { ErrorBanner } from '../components/ErrorBanner'

export function MemoryHitRate() {
  const { data, isLoading, error } = useMemoryHitRate()

  if (isLoading) return <LoadingSpinner />
  if (error || !data) return <ErrorBanner message="Failed to load memory hit rate" />
  if (!data.total_calls) return <p className="text-gray-400 text-sm py-6">No memory recall calls recorded yet.</p>

  const chart = [
    { name: 'Hits', value: data.hits, color: '#10b981' },
    { name: 'Misses', value: data.misses, color: '#f87171' },
  ]

  return (
    <section>
      <h2 className="text-lg font-semibold text-gray-800 mb-3">Memory Hit Rate</h2>
      <div className="flex items-center gap-8">
        <ResponsiveContainer width={180} height={180}>
          <PieChart>
            <Pie data={chart} cx="50%" cy="50%" innerRadius={50} outerRadius={80} dataKey="value" strokeWidth={0}>
              {chart.map((entry, i) => <Cell key={i} fill={entry.color} />)}
            </Pie>
            <Tooltip formatter={(v: number) => [v, '']} />
          </PieChart>
        </ResponsiveContainer>
        <div>
          <p className="text-3xl font-bold text-gray-900">{data.hit_rate_pct.toFixed(1)}%</p>
          <p className="text-sm text-gray-500 mt-1">hit rate</p>
          <p className="text-sm text-gray-400 mt-3">
            {data.hits} of {data.total_calls} recall calls returned a match
          </p>
          <div className="flex gap-4 mt-3 text-xs text-gray-500">
            <span className="flex items-center gap-1"><span className="inline-block w-3 h-3 rounded-full bg-emerald-500" />Hits ({data.hits})</span>
            <span className="flex items-center gap-1"><span className="inline-block w-3 h-3 rounded-full bg-red-400" />Misses ({data.misses})</span>
          </div>
        </div>
      </div>
    </section>
  )
}
