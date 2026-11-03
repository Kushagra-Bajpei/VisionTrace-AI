/**
 * Search Service – Typed client methods for Natural Language CCTV Search.
 */
import apiClient from './api'
import type {
  SearchQueryRequest,
  SearchQueryResponse,
  SearchSuggestion,
} from '@/types'

export const searchService = {
  /**
   * Execute natural language query with structured facets.
   */
  async searchQuery(payload: SearchQueryRequest): Promise<SearchQueryResponse> {
    const res = await apiClient.post<SearchQueryResponse>('/search/query', payload)
    return res.data
  },

  /**
   * Quick GET natural language search query.
   */
  async quickSearch(
    q: string,
    params?: { video_id?: string; min_confidence?: number; time_min?: number; time_max?: number },
  ): Promise<SearchQueryResponse> {
    const res = await apiClient.get<SearchQueryResponse>('/search/quick', {
      params: { q, ...params },
    })
    return res.data
  },

  /**
   * Retrieve operator query templates.
   */
  async getSuggestions(): Promise<SearchSuggestion[]> {
    const res = await apiClient.get<SearchSuggestion[]>('/search/suggestions')
    return res.data
  },
}
