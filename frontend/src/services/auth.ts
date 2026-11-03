/**
 * Authentication, RBAC, Media Tokens, Audit & Integrity API Service.
 */
import apiClient from './api'
import type {
  AuditLog,
  IntegrityVerificationResult,
  MediaTokenResponse,
  TokenResponse,
  User,
  UserRole,
} from '@/types'

export const authService = {
  /**
   * Initial setup: Bootstrap first administrator.
   */
  async bootstrapAdmin(payload: { email: string; password: string; full_name?: string }): Promise<TokenResponse> {
    const res = await apiClient.post<TokenResponse>('/auth/bootstrap-admin', payload)
    return res.data
  },

  /**
   * Register a new operator account.
   */
  async register(payload: { email: string; password: string; full_name?: string }): Promise<TokenResponse> {
    const res = await apiClient.post<TokenResponse>('/auth/register', payload)
    return res.data
  },

  /**
   * Authenticate with email and password.
   */
  async login(payload: { email: string; password: string }): Promise<TokenResponse> {
    const res = await apiClient.post<TokenResponse>('/auth/login', payload)
    return res.data
  },

  /**
   * Invalidate token and persist revocation.
   */
  async logout(): Promise<void> {
    await apiClient.post('/auth/logout')
  },

  /**
   * Fetch currently authenticated user profile.
   */
  async getMe(): Promise<User> {
    const res = await apiClient.get<User>('/auth/me')
    return res.data
  },

  /**
   * Acquire a scoped, short-lived media token for <img>, <video>, and downloads.
   */
  async getMediaToken(resourceType: 'video' | 'frame' | 'crop' | 'report', resourceId: string): Promise<string> {
    const res = await apiClient.post<MediaTokenResponse>('/auth/media-token', {
      resource_type: resourceType,
      resource_id: resourceId,
    })
    return res.data.media_token
  },

  /**
   * List all user accounts (Admins & Reviewers).
   */
  async getUsers(): Promise<User[]> {
    const res = await apiClient.get<User[]>('/auth/users')
    return res.data
  },

  /**
   * Update a user's authorization role (Admin only).
   */
  async updateUserRole(userId: string, role: UserRole): Promise<User> {
    const res = await apiClient.patch<User>(`/auth/users/${userId}/role`, { role })
    return res.data
  },

  /**
   * Fetch audit activity logs (Admin only).
   */
  async getAuditLogs(params?: {
    action?: string
    target_type?: string
    limit?: number
    offset?: number
  }): Promise<AuditLog[]> {
    const res = await apiClient.get<AuditLog[]>('/audit', { params })
    return res.data
  },

  /**
   * Cryptographically verify video file SHA-256 integrity against disk storage.
   */
  async verifyVideoIntegrity(videoId: string): Promise<IntegrityVerificationResult> {
    const res = await apiClient.post<IntegrityVerificationResult>(`/videos/${videoId}/verify-integrity`)
    return res.data
  },

  /**
   * Cryptographically verify evidence crop/frame SHA-256 integrity against disk storage.
   */
  async verifyEvidenceIntegrity(caseId: string, evidenceId: string): Promise<IntegrityVerificationResult> {
    const res = await apiClient.post<IntegrityVerificationResult>(
      `/cases/${caseId}/evidence/${evidenceId}/verify-integrity`
    )
    return res.data
  },

  /**
   * Cryptographically verify PDF report SHA-256 integrity against disk storage.
   */
  async verifyReportIntegrity(caseId: string, reportId: string): Promise<IntegrityVerificationResult> {
    const res = await apiClient.post<IntegrityVerificationResult>(
      `/cases/${caseId}/reports/${reportId}/verify-integrity`
    )
    return res.data
  },
}
