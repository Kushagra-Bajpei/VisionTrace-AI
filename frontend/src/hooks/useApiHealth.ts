/**
 * Hook – polls the backend health endpoints and tracks connectivity.
 * Used by Header and Dashboard to show real-time API and subsystem status.
 */
import { useQuery } from '@tanstack/react-query'
import { healthService } from '@/services/health'

export function useApiHealth() {
  const { data, isError, isLoading } = useQuery({
    queryKey: ['health'],
    queryFn: healthService.getHealth,
    refetchInterval: 30_000, // poll every 30s
    retry: 1,
    staleTime: 15_000,
  })

  return {
    health: data,
    isConnected: !isError && !isLoading && data?.status === 'ok',
    isLoading,
    isError,
  }
}

export function useDetailedHealth() {
  const { data, isError, isLoading } = useQuery({
    queryKey: ['health', 'detailed'],
    queryFn: healthService.getDetailedHealth,
    refetchInterval: 30_000,
    retry: 1,
    staleTime: 15_000,
  })

  return {
    detailedHealth: data,
    isLoading,
    isError,
  }
}
