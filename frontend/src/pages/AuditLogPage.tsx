/**
 * VisionTrace AI – Security & Forensic Audit Trail Viewer (Phase 8).
 * Displays immutable system logs for case access, auth events, integrity checks, and role changes.
 */
import React, { useEffect, useState } from 'react'
import { ShieldCheck, RefreshCw, Filter, AlertTriangle, CheckCircle, Clock, Terminal } from 'lucide-react'
import { authService } from '@/services/auth'
import type { AuditLog } from '@/types'

export const AuditLogPage: React.FC = () => {
  const [logs, setLogs] = useState<AuditLog[]>([])
  const [loading, setLoading] = useState<boolean>(true)
  const [error, setError] = useState<string | null>(null)
  const [actionFilter, setActionFilter] = useState<string>('')
  const [targetTypeFilter, setTargetTypeFilter] = useState<string>('')

  const fetchLogs = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await authService.getAuditLogs({
        action: actionFilter || undefined,
        target_type: targetTypeFilter || undefined,
        limit: 100,
      })
      setLogs(data)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to retrieve audit log records')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchLogs()
  }, [actionFilter, targetTypeFilter])

  const getOutcomeBadge = (outcome: string) => {
    switch (outcome.toLowerCase()) {
      case 'success':
        return (
          <span className="inline-flex items-center gap-1 text-[11px] font-mono font-semibold text-emerald-400 bg-emerald-950/60 border border-emerald-500/30 px-2 py-0.5 rounded">
            <CheckCircle className="w-3 h-3 text-emerald-400" />
            SUCCESS
          </span>
        )
      case 'denied':
        return (
          <span className="inline-flex items-center gap-1 text-[11px] font-mono font-semibold text-red-400 bg-red-950/60 border border-red-500/30 px-2 py-0.5 rounded">
            <AlertTriangle className="w-3 h-3 text-red-400" />
            DENIED
          </span>
        )
      default:
        return (
          <span className="inline-flex items-center gap-1 text-[11px] font-mono font-semibold text-amber-400 bg-amber-950/60 border border-amber-500/30 px-2 py-0.5 rounded">
            <Clock className="w-3 h-3 text-amber-400" />
            {outcome.toUpperCase()}
          </span>
        )
    }
  }

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6 font-sans">
      {/* Title Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-800">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <ShieldCheck className="w-5 h-5 text-cyan-400" />
            <h1 className="text-xl font-bold tracking-wide text-slate-100 uppercase font-mono">
              Cryptographic Audit Trail
            </h1>
          </div>
          <p className="text-xs text-slate-400">
            Immutable, synchronized ledger of all case access, evidence modifications, integrity checks, and authentication events.
          </p>
        </div>

        <button
          onClick={fetchLogs}
          disabled={loading}
          className="self-start sm:self-auto flex items-center gap-2 px-3 py-1.5 bg-[#0e1420] border border-cyan-500/30 text-cyan-400 hover:bg-cyan-950/50 rounded-lg text-xs font-mono uppercase tracking-wider transition-all disabled:opacity-50 cursor-pointer"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          <span>Refresh Ledger</span>
        </button>
      </div>

      {/* Filter Controls */}
      <div className="flex flex-wrap items-center gap-3 bg-[#0a0d14] p-3 rounded-lg border border-slate-800 text-xs font-mono">
        <div className="flex items-center gap-2 text-slate-400">
          <Filter className="w-3.5 h-3.5 text-cyan-400" />
          <span>FILTER:</span>
        </div>

        <select
          value={actionFilter}
          onChange={(e) => setActionFilter(e.target.value)}
          className="bg-[#10141e] border border-slate-800 text-slate-300 rounded px-2.5 py-1 focus:outline-none focus:border-cyan-500/50"
        >
          <option value="">All Actions</option>
          <option value="auth.login">Auth Login</option>
          <option value="auth.logout">Auth Logout</option>
          <option value="case_create">Case Create</option>
          <option value="case_update">Case Update</option>
          <option value="case_delete">Case Delete</option>
          <option value="evidence_add">Evidence Add</option>
          <option value="evidence_integrity_verify">Evidence Integrity Verify</option>
          <option value="video_integrity_verify">Video Integrity Verify</option>
          <option value="report_generate">Report Generate</option>
          <option value="report_download">Report Download</option>
        </select>

        <select
          value={targetTypeFilter}
          onChange={(e) => setTargetTypeFilter(e.target.value)}
          className="bg-[#10141e] border border-slate-800 text-slate-300 rounded px-2.5 py-1 focus:outline-none focus:border-cyan-500/50"
        >
          <option value="">All Target Types</option>
          <option value="investigation">Investigation</option>
          <option value="investigation_evidence">Evidence</option>
          <option value="video">Video</option>
          <option value="report">Report</option>
          <option value="user">User</option>
          <option value="auth">Auth</option>
        </select>

        <span className="ml-auto text-slate-500 text-[11px]">
          Showing {logs.length} records
        </span>
      </div>

      {error && (
        <div className="p-3 bg-red-950/40 border border-red-500/30 rounded-lg text-red-300 text-xs">
          {error}
        </div>
      )}

      {/* Audit Log Table */}
      <div className="bg-[#0b0e16] border border-slate-800/80 rounded-xl overflow-hidden shadow-xl">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="bg-[#080b11] border-b border-slate-800 text-slate-400 font-mono uppercase text-[11px]">
                <th className="py-3 px-4">Timestamp (UTC)</th>
                <th className="py-3 px-4">Actor</th>
                <th className="py-3 px-4">Action</th>
                <th className="py-3 px-4">Target</th>
                <th className="py-3 px-4">Outcome</th>
                <th className="py-3 px-4">Client IP</th>
                <th className="py-3 px-4">Metadata</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/50 font-mono">
              {logs.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-8 text-center text-slate-500">
                    {loading ? 'Retrieving cryptographic audit logs...' : 'No audit records match the selected criteria.'}
                  </td>
                </tr>
              ) : (
                logs.map((log) => (
                  <tr key={log.id} className="hover:bg-cyan-950/10 transition-colors">
                    <td className="py-2.5 px-4 text-slate-400 whitespace-nowrap text-[11px]">
                      {new Date(log.created_at).toISOString().replace('T', ' ').slice(0, 19)}
                    </td>
                    <td className="py-2.5 px-4 text-slate-200 whitespace-nowrap">
                      {log.actor_email ? (
                        <span className="text-cyan-300 font-medium">{log.actor_email}</span>
                      ) : (
                        <span className="text-slate-500 italic">SYSTEM</span>
                      )}
                    </td>
                    <td className="py-2.5 px-4 text-slate-100 font-semibold">
                      {log.action}
                    </td>
                    <td className="py-2.5 px-4 text-slate-400 whitespace-nowrap">
                      <span className="px-1.5 py-0.5 rounded bg-slate-900 border border-slate-800 text-[10px] text-slate-300 uppercase">
                        {log.target_type}
                      </span>
                      {log.target_id && (
                        <span className="ml-1.5 text-slate-500 text-[11px]">
                          #{log.target_id.slice(0, 8)}
                        </span>
                      )}
                    </td>
                    <td className="py-2.5 px-4 whitespace-nowrap">
                      {getOutcomeBadge(log.outcome)}
                    </td>
                    <td className="py-2.5 px-4 text-slate-500 whitespace-nowrap text-[11px]">
                      {log.client_ip || 'Internal'}
                    </td>
                    <td className="py-2.5 px-4 text-slate-400 max-w-xs truncate text-[11px]">
                      {log.details ? JSON.stringify(log.details) : '—'}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
