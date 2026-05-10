import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts'
import { useSavings } from '../hooks/useQueries'
import { StatCard } from '../components/StatCard'
import { LoadingSpinner } from '../components/LoadingSpinner'
import { ErrorBanner } from '../components/ErrorBanner'

export function TokenSavings() {
  const { data, isLoading, error } = useSavings()

  if (isLoading) return <LoadingSpinner />
  if (error || !data) return <ErrorBanner message="Failed to load savings data" />
  if (!data.total_tokens_saved) return <p className="text-gray-400 text-sm py-6">No savings recorded yet. Use codedrift tools in your AI agent sessions.</p>

  const totalK = (data.total_tokens_saved / 1000).toFixed(1)
  const chart = data.over_time.map(r => ({ date: r.date.slice(5), cumulative: Math.round(r.cumulative_saved / 1000) }))

  return (
    <section>
      <h2 className="text-lg font-semibold text-gray-800 mb-3">Token Savings</h2>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-5">
        <StatCard label="Total Tokens Saved" value={`${totalK}K`} />
        {data.by_tool.slice(0, 3).map(t => (
          <StatCard key={t.tool} label={t.tool.replace('codedrift_', '')} value={`${(t.tokens_saved / 1000).toFixed(1)}K`} sub="tokens saved" />
        ))}
      </div>
      <ResponsiveContainer width="100%" height={200}>
        <AreaChart data={chart} margin={{ top: 4, right: 16, left: 0, bottom: 4 }}>
          <defs>
            <linearGradient id="savingsGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#10b981" stopOpacity={0.25} />
              <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
          <XAxis dataKey="date" tick={{ fontSize: 11 }} />
          <YAxis tick={{ fontSize: 11 }} label={{ value: 'K tokens', angle: -90, position: 'insideLeft', offset: 10, fontSize: 11 }} />
          <Tooltip formatter={(v: number) => [`${v}K`, 'Cumulative Saved']} />
          <Area type="monotone" dataKey="cumulative" stroke="#10b981" fill="url(#savingsGrad)" strokeWidth={2} />
        </AreaChart>
      </ResponsiveContainer>
    </section>
  )
}
