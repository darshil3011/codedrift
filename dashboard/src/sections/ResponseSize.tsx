import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, LineChart, Line } from 'recharts'
import { useResponseSize } from '../hooks/useQueries'
import { LoadingSpinner } from '../components/LoadingSpinner'
import { ErrorBanner } from '../components/ErrorBanner'

export function ResponseSize() {
  const { data, isLoading, error } = useResponseSize()

  if (isLoading) return <LoadingSpinner />
  if (error || !data) return <ErrorBanner message="Failed to load response size data" />
  if (!data.length) return <p className="text-gray-400 text-sm py-6">No response data recorded yet.</p>

  const summary = data.map(r => ({ tool: r.tool.replace('codedrift_', ''), avg: Math.round(r.avg_output_tokens) }))

  return (
    <section>
      <h2 className="text-lg font-semibold text-gray-800 mb-3">Average Response Size by Tool</h2>
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={summary} margin={{ top: 4, right: 16, left: 0, bottom: 4 }}>
          <XAxis dataKey="tool" tick={{ fontSize: 12 }} />
          <YAxis tick={{ fontSize: 11 }} label={{ value: 'Avg tokens', angle: -90, position: 'insideLeft', offset: 10, fontSize: 11 }} />
          <Tooltip formatter={(v) => [v, 'Avg output tokens']} />
          <Bar dataKey="avg" name="Avg Output Tokens" fill="#6366f1" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
      {data.some(r => r.trend.length > 1) && (
        <div className="mt-6 grid grid-cols-2 md:grid-cols-3 gap-4">
          {data.filter(r => r.trend.length > 1).map(r => (
            <div key={r.tool} className="border border-gray-100 rounded-lg p-3">
              <p className="text-xs text-gray-500 mb-2">{r.tool.replace('codedrift_', '')} trend</p>
              <ResponsiveContainer width="100%" height={60}>
                <LineChart data={r.trend}>
                  <Line type="monotone" dataKey="avg" stroke="#6366f1" dot={false} strokeWidth={1.5} />
                  <Tooltip formatter={(v) => [`${Math.round(Number(v))} tokens`, '']} labelFormatter={l => String(l).slice(5)} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}
