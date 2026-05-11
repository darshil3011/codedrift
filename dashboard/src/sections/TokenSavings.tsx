import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts'
import { useSavings } from '../hooks/useQueries'
import { StatCard } from '../components/StatCard'
import { LoadingSpinner } from '../components/LoadingSpinner'
import { ErrorBanner } from '../components/ErrorBanner'

const COST_PER_TOKEN = 5 / 1_000_000  // $5 per 1M tokens

function formatCost(tokens: number): string {
  const dollars = tokens * COST_PER_TOKEN
  if (dollars >= 1000) return `$${(dollars / 1000).toFixed(1)}K`
  if (dollars >= 1) return `$${dollars.toFixed(2)}`
  return `$${dollars.toFixed(4)}`
}

export function TokenSavings() {
  const { data, isLoading, error } = useSavings()

  if (isLoading) return <LoadingSpinner />
  if (error || !data) return <ErrorBanner message="Failed to load savings data" />
  if (!data.total_tokens_saved) return (
    <p className="text-gray-400 text-sm py-6">No savings recorded yet. Use codedrift tools in your AI agent sessions.</p>
  )

  const totalTokens = data.total_tokens_saved
  const totalK = (totalTokens / 1000).toFixed(1)
  const totalCost = formatCost(totalTokens)
  const chart = data.over_time.map(r => ({
    date: r.date.slice(5),
    cumulative: Math.round(r.cumulative_saved / 1000),
    cost: parseFloat((r.cumulative_saved * COST_PER_TOKEN).toFixed(2)),
  }))

  return (
    <section>
      <h2 className="text-lg font-semibold text-gray-800 mb-3">Token Savings</h2>

      {/* Hero stat row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <div className="col-span-1 bg-emerald-50 border border-emerald-200 rounded-xl p-5 flex flex-col gap-1">
          <span className="text-emerald-600 text-sm">Total Tokens Saved</span>
          <span className="text-2xl font-bold text-emerald-700">{totalK}K</span>
        </div>
        <div className="col-span-1 bg-blue-50 border border-blue-200 rounded-xl p-5 flex flex-col gap-1">
          <span className="text-blue-600 text-sm">Estimated Cost Saved</span>
          <span className="text-2xl font-bold text-blue-700">{totalCost}</span>
          <span className="text-xs text-blue-400">at $5 / 1M tokens</span>
        </div>
        {data.by_tool.slice(0, 2).map(t => (
          <div key={t.tool} className="bg-white border border-gray-200 rounded-xl p-5 flex flex-col gap-1">
            <span className="text-gray-500 text-sm">{t.tool.replace('codedrift_', '')}</span>
            <span className="text-2xl font-semibold text-gray-900">{(t.tokens_saved / 1000).toFixed(1)}K</span>
            <span className="text-xs text-gray-400">{formatCost(t.tokens_saved)} saved</span>
          </div>
        ))}
      </div>

      {/* Per-tool savings breakdown */}
      {data.by_tool.length > 2 && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          {data.by_tool.slice(2).map(t => (
            <StatCard
              key={t.tool}
              label={t.tool.replace('codedrift_', '')}
              value={`${(t.tokens_saved / 1000).toFixed(1)}K`}
              sub={`${formatCost(t.tokens_saved)} saved`}
            />
          ))}
        </div>
      )}

      {/* Cumulative chart */}
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
          <Tooltip
            formatter={(v, name) =>
              name === 'cumulative' ? [`${v}K tokens`, 'Cumulative Saved'] : [`$${v}`, 'Cost Saved']
            }
          />
          <Area type="monotone" dataKey="cumulative" name="cumulative" stroke="#10b981" fill="url(#savingsGrad)" strokeWidth={2} />
        </AreaChart>
      </ResponsiveContainer>
    </section>
  )
}
