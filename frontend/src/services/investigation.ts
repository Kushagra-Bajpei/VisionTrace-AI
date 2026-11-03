/**
 * Investigation Cases, Evidence & Reports API Client (Phase 7).
 */
import { apiClient } from '@/services/api'
import type {
  CaseCreatePayload,
  CaseReport,
  CaseUpdatePayload,
  EvidenceAddPayload,
  EvidenceUpdatePayload,
  InvestigationCase,
  InvestigationEvidence,
  InvestigationMessage,
  ReportGeneratePayload,
} from '@/types'

export interface CaseListFilters {
  status?: string
  priority?: string
  search?: string
  skip?: number
  limit?: number
}

export const investigationService = {
  /**
   * List all investigation cases with optional status, priority, or search filters.
   */
  async listCases(filters: CaseListFilters = {}): Promise<InvestigationCase[]> {
    const params: Record<string, unknown> = {}
    if (filters.status && filters.status !== 'all') params.status = filters.status
    if (filters.priority && filters.priority !== 'all') params.priority = filters.priority
    if (filters.search) params.search = filters.search
    if (filters.skip !== undefined) params.skip = filters.skip
    if (filters.limit !== undefined) params.limit = filters.limit

    const { data } = await apiClient.get<InvestigationCase[]>('/cases', { params })
    return data
  },

  /**
   * Retrieve single case details including evidence items and messages.
   */
  async getCase(caseId: string): Promise<InvestigationCase> {
    const { data } = await apiClient.get<InvestigationCase>(`/cases/${caseId}`)
    return data
  },

  /**
   * Create a new investigation case.
   */
  async createCase(payload: CaseCreatePayload): Promise<InvestigationCase> {
    const { data } = await apiClient.post<InvestigationCase>('/cases', payload)
    return data
  },

  /**
   * Update case metadata (title, description, status, priority, tags).
   */
  async updateCase(caseId: string, payload: CaseUpdatePayload): Promise<InvestigationCase> {
    const { data } = await apiClient.patch<InvestigationCase>(`/cases/${caseId}`, payload)
    return data
  },

  /**
   * Delete an investigation case and associated case artifacts.
   */
  async deleteCase(caseId: string): Promise<{ success: boolean; message: string }> {
    const { data } = await apiClient.delete<{ success: boolean; message: string }>(`/cases/${caseId}`)
    return data
  },

  /**
   * Add evidence item to a case (with duplicate prevention).
   */
  async addEvidence(caseId: string, payload: EvidenceAddPayload): Promise<InvestigationEvidence> {
    const { data } = await apiClient.post<InvestigationEvidence>(`/cases/${caseId}/evidence`, payload)
    return data
  },

  /**
   * List evidence items for a case.
   */
  async listEvidence(caseId: string): Promise<InvestigationEvidence[]> {
    const { data } = await apiClient.get<InvestigationEvidence[]>(`/cases/${caseId}/evidence`)
    return data
  },

  /**
   * Update notes or sequence order for an evidence item.
   */
  async updateEvidence(
    caseId: string,
    evidenceId: string,
    payload: EvidenceUpdatePayload
  ): Promise<InvestigationEvidence> {
    const { data } = await apiClient.patch<InvestigationEvidence>(
      `/cases/${caseId}/evidence/${evidenceId}`,
      payload
    )
    return data
  },

  /**
   * Remove an evidence item from an investigation case.
   */
  async deleteEvidence(
    caseId: string,
    evidenceId: string
  ): Promise<{ success: boolean; message: string }> {
    const { data } = await apiClient.delete<{ success: boolean; message: string }>(
      `/cases/${caseId}/evidence/${evidenceId}`
    )
    return data
  },

  /**
   * Add an investigator note or activity message to the case log.
   */
  async addCaseNote(
    caseId: string,
    payload: { message: string; sender_type?: string }
  ): Promise<InvestigationMessage> {
    const { data } = await apiClient.post<InvestigationMessage>(`/cases/${caseId}/notes`, payload)
    return data
  },

  /**
   * Generate a forensic PDF report for the case.
   */
  async generateReport(
    caseId: string,
    payload: ReportGeneratePayload = {}
  ): Promise<CaseReport> {
    const { data } = await apiClient.post<CaseReport>(`/cases/${caseId}/report`, payload)
    return data
  },

  /**
   * List all generated PDF reports for this case.
   */
  async listReports(caseId: string): Promise<CaseReport[]> {
    const { data } = await apiClient.get<CaseReport[]>(`/cases/${caseId}/reports`)
    return data
  },

  /**
   * List all forensic reports generated across all cases accessible to user.
   */
  async listAllReports(): Promise<CaseReport[]> {
    const { data } = await apiClient.get<CaseReport[]>('/cases/reports/archive')
    return data
  },
}
