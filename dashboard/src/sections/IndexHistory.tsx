import { useIndexHistory } from '../hooks/useQueries'
import { LoadingSpinner } from '../components/LoadingSpinner'
import { ErrorBanner } from '../components/ErrorBanner'

export function IndexHistory() {
  const { data, isLoading, error } = useIndexHistory()

  if (isLoading) return <LoadingSpinner />
  if (error || !data) return <ErrorBanner message="Failed to load index history" />
  if (!data.length) return <p className="text-gray-400 text-sm py-6">No index history yet. Run <code className="font-mono bg-gray-100 px-1 rounded">codedrift init</code>.</p>

  return (
    <section>
      <h2 className="text-lg font-semibold text-gray-800 mb-3">Init / Update History</h2>
      <div className="overflow-x-auto rounded-lg border border-gray-200">
        <table className="w-full text-sm text-left">
          <thead className="bg-gray-50 text-gray-500 text-xs uppercase">
            <tr>
              {['Type', 'Time', 'Duration', 'Files Indexed', 'Files Skipped', 'Symbols', 'Mode'].map(h => (
                <th key={h} className="px-4 py-2 font-medium">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {data.map(row => (
              <tr key={row.id} className="hover:bg-gray-50">
                <td className="px-4 py-2 font-medium capitalize">{row.event_type}</td>
                <td className="px-4 py-2 text-gray-500">{new Date(row.timestamp * 1000).toLocaleString()}</td>
                <td className="px-4 py-2">{row.duration_ms != null ? `${(row.duration_ms / 1000).toFixed(1)}s` : '—'}</td>
                <td className="px-4 py-2">{row.files_indexed.toLocaleString()}</td>
                <td className="px-4 py-2">{row.files_skipped.toLocaleString()}</td>
                <td className="px-4 py-2">{row.symbols.toLocaleString()}</td>
                <td className="px-4 py-2">{row.incremental ? 'Incremental' : 'Full'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}
