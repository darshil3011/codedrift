import { useStats } from '../hooks/useQueries'
import { StatCard } from '../components/StatCard'
import { FreshnessWarning } from '../components/FreshnessWarning'
import { LoadingSpinner } from '../components/LoadingSpinner'
import { ErrorBanner } from '../components/ErrorBanner'

export function IndexHealth() {
  const { data, isLoading, error } = useStats()

  if (isLoading) return <LoadingSpinner />
  if (error || !data) return <ErrorBanner message="Failed to load index stats" />

  const topLang = Object.entries(data.languages).sort((a, b) => b[1] - a[1]).slice(0, 3)
    .map(([l, n]) => `${l} (${n})`).join(', ')

  const lastIndexed = data.last_indexed
    ? new Date(data.last_indexed * 1000).toLocaleString()
    : 'Never'

  return (
    <section>
      <h2 className="text-lg font-semibold text-gray-800 mb-3">Index Health</h2>
      {data.index_age_hours != null && <div className="mb-4"><FreshnessWarning hours={data.index_age_hours} /></div>}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard label="Files Indexed" value={data.files.toLocaleString()} />
        <StatCard label="Symbols" value={data.symbols.toLocaleString()} />
        <StatCard label="Top Languages" value={topLang || '—'} />
        <StatCard label="Last Indexed" value={lastIndexed} />
      </div>
    </section>
  )
}
