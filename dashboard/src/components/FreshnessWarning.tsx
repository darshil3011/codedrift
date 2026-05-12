interface FreshnessWarningProps { hours: number }

export function FreshnessWarning({ hours }: FreshnessWarningProps) {
  if (hours <= 24) return null
  const days = (hours / 24).toFixed(1)
  return (
    <div className="rounded-lg bg-amber-50 border border-amber-300 text-amber-800 px-4 py-3 text-sm flex items-center gap-2">
      <span className="text-lg">⚠️</span>
      Index is <strong>{days} days</strong> old — run <code className="font-mono bg-amber-100 px-1 rounded">codedrift update</code> to refresh.
    </div>
  )
}
