import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'

const FIVE_MIN = 5 * 60 * 1000
const THIRTY_SEC = 30 * 1000

export const useStats = () =>
  useQuery({ queryKey: ['stats'], queryFn: api.stats, refetchInterval: THIRTY_SEC })

export const useToolSummary = () =>
  useQuery({ queryKey: ['toolSummary'], queryFn: api.toolSummary, staleTime: FIVE_MIN })

export const useToolTimeline = (days = 30) =>
  useQuery({ queryKey: ['toolTimeline', days], queryFn: () => api.toolTimeline(days), staleTime: FIVE_MIN })

export const useIndexHistory = () =>
  useQuery({ queryKey: ['indexHistory'], queryFn: api.indexHistory, staleTime: FIVE_MIN })

export const useSavings = () =>
  useQuery({ queryKey: ['savings'], queryFn: api.savings, staleTime: FIVE_MIN })

export const useSymbolHeatmap = () =>
  useQuery({ queryKey: ['symbolHeatmap'], queryFn: () => api.symbolHeatmap(20), staleTime: FIVE_MIN })

export const useMemoryHitRate = () =>
  useQuery({ queryKey: ['memoryHitRate'], queryFn: api.memoryHitRate, staleTime: FIVE_MIN })

export const useResponseSize = () =>
  useQuery({ queryKey: ['responseSize'], queryFn: api.responseSize, staleTime: FIVE_MIN })
