interface ErrorBannerProps { message?: string }

export function ErrorBanner({ message = 'Failed to load data' }: ErrorBannerProps) {
  return (
    <div className="rounded-lg bg-red-50 border border-red-200 text-red-700 px-4 py-3 text-sm">
      {message}
    </div>
  )
}
