const BASE = '/api'

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json()
}

export interface Stats {
  files: number
  symbols: number
  languages: Record<string, number>
  last_indexed: number | null
  index_age_hours: number | null
}

export interface ToolSummaryRow {
  tool: string
  call_count: number
  total_tokens_saved: number
}

export interface TimelineRow {
  date: string
  call_count: number
  tokens_saved: number
}

export interface IndexHistoryRow {
  id: number
  event_type: string
  timestamp: number
  duration_ms: number
  files_indexed: number
  files_skipped: number
  symbols: number
  incremental: boolean
}

export interface SavingsSummary {
  total_tokens_saved: number
  by_tool: { tool: string; tokens_saved: number }[]
  over_time: { date: string; cumulative_saved: number }[]
}

export interface SymbolHeatmapRow {
  symbol: string
  call_count: number
  file: string | null
  kind: string | null
}

export interface MemoryHitRate {
  total_calls: number
  hits: number
  misses: number
  hit_rate_pct: number
}

export interface ResponseSizeRow {
  tool: string
  avg_output_tokens: number
  trend: { date: string; avg: number }[]
}

export const api = {
  health: () => get<{ status: string; db_size_bytes: number }>('/health'),
  stats: () => get<Stats>('/stats'),
  toolSummary: () => get<ToolSummaryRow[]>('/tools/summary'),
  toolTimeline: (days = 30) => get<TimelineRow[]>(`/tools/timeline?days=${days}`),
  indexHistory: () => get<IndexHistoryRow[]>('/index/history'),
  savings: () => get<SavingsSummary>('/savings'),
  symbolHeatmap: (limit = 20) => get<SymbolHeatmapRow[]>(`/symbols/heatmap?limit=${limit}`),
  memoryHitRate: () => get<MemoryHitRate>('/memory/hit-rate'),
  responseSize: () => get<ResponseSizeRow[]>('/tools/response-size'),
}
