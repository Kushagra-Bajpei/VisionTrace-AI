/**
 * Health service – typed wrappers for health-check API calls.
 */
import apiClient from './api'
import type { HealthStatus, DetailedHealthStatus } from '@/types'

export const healthService = {
  async getHealth(): Promise<HealthStatus> {
    const res = await apiClient.get<HealthStatus>('/health')
    return res.data
  },

  async getDetailedHealth(): Promise<DetailedHealthStatus> {
    const res = await apiClient.get<DetailedHealthStatus>('/health/detailed')
    return res.data
  },
}
