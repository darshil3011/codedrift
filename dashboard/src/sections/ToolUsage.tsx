import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend } from 'recharts'
import { useToolSummary } from '../hooks/useQueries'
import { LoadingSpinner } from '../components/LoadingSpinner'
import { ErrorBanner } from '../components/ErrorBanner'

export function ToolUsage() {
  const { data, isLoading, error } = useToolSummary()

  if (isLoading) return <LoadingSpinner />
  if (error || !data) return <ErrorBanner message="Failed to load tool usage" />
  if (!data.length) return <p className="text-gray-400 text-sm py-6">No tool calls recorded yet. Run a codedrift search to start tracking.</p>

  const chart = data.map(r => ({
    tool: r.tool.replace('codedrift_', ''),
    calls: r.call_count,
    saved: Math.round(r.total_tokens_saved / 1000),
  }))

  return (
    <section>
      <h2 className="text-lg font-semibold text-gray-800 mb-3">Tool Usage</h2>
      <ResponsiveContainer width="100%" height={260}>
        <BarChart data={chart} margin={{ top: 4, right: 16, left: 0, bottom: 4 }}>
          <XAxis dataKey="tool" tick={{ fontSize: 12 }} />
          <YAxis yAxisId="left" tick={{ fontSize: 12 }} />
          <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 12 }} label={{ value: 'K tokens saved', angle: -90, position: 'insideRight', offset: 10, fontSize: 11 }} />
          <Tooltip />
          <Legend />
          <Bar yAxisId="left" dataKey="calls" name="Call Count" fill="#6366f1" radius={[4, 4, 0, 0]} />
          <Bar yAxisId="right" dataKey="saved" name="Tokens Saved (K)" fill="#10b981" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </section>
  )
}
