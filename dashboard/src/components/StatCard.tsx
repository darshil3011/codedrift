interface StatCardProps {
  label: string
  value: string | number
  sub?: string
  icon?: React.ReactNode
}

export function StatCard({ label, value, sub, icon }: StatCardProps) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5 flex flex-col gap-1">
      <div className="flex items-center justify-between text-gray-500 text-sm">
        <span>{label}</span>
        {icon && <span className="text-gray-400">{icon}</span>}
      </div>
      <div className="text-2xl font-semibold text-gray-900">{value}</div>
      {sub && <div className="text-xs text-gray-400">{sub}</div>}
    </div>
  )
}
