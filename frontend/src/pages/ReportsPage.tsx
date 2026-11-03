/**
 * ReportsPage – Forensic Incident Reports & Evidence Archive.
 * Displays all generated evidentiary PDF dossiers, SHA-256 cryptographic seals,
 * live integrity verification, and scoped tokenized forensic downloads.
 */
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  FileText,
  Download,
  ShieldCheck,
  CheckCircle2,
  AlertTriangle,
  RotateCw,
  ExternalLink,
  Search,
  FolderSearch,
  Lock,
  Layers,
  Calendar,
  FileCheck2,
} from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { investigationService } from '@/services/investigation'
import { authService } from '@/services/auth'
import { formatDateTime } from '@/lib/utils'
import type { CaseReport, IntegrityVerificationResult } from '@/types'

export function ReportsPage() {
  const [reports, setReports] = useState<CaseReport[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const [isVerifying, setIsVerifying] = useState<Record<string, boolean>>({})
  const [verifyResults, setVerifyResults] = useState<Record<string, IntegrityVerificationResult>>({})
  const [isDownloading, setIsDownloading] = useState<Record<string, boolean>>({})

  const loadReports = async () => {
    setIsLoading(true)
    try {
      const data = await investigationService.listAllReports()
      setReports(data)
    } catch (err) {
      console.error('Failed to load forensic reports:', err)
      setReports([])
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    loadReports()
  }, [])

  const handleVerify = async (caseId: string, reportId: string) => {
    setIsVerifying((prev) => ({ ...prev, [reportId]: true }))
    try {
      const res = await authService.verifyReportIntegrity(caseId, reportId)
      setVerifyResults((prev) => ({ ...prev, [reportId]: res }))
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Cryptographic integrity verification failed')
    } finally {
      setIsVerifying((prev) => ({ ...prev, [reportId]: false }))
    }
  }

  const handleDownload = async (report: CaseReport) => {
    setIsDownloading((prev) => ({ ...prev, [report.id]: true }))
    try {
      const mediaToken = await authService.getMediaToken('report', report.id)
      const downloadBase = report.download_url || `/api/v1/cases/${report.investigation_id}/reports/${report.id}/download`
      const secureUrl = `${downloadBase}?media_token=${encodeURIComponent(mediaToken)}`

      const a = document.createElement('a')
      a.href = secureUrl
      a.download = `forensic_report_${report.id.slice(0, 8)}.pdf`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to authorize forensic report download')
    } finally {
      setIsDownloading((prev) => ({ ...prev, [report.id]: false }))
    }
  }

  const filteredReports = reports.filter((r) => {
    if (!searchQuery) return true
    const q = searchQuery.toLowerCase()
    return (
      r.title.toLowerCase().includes(q) ||
      (r.case_title && r.case_title.toLowerCase().includes(q)) ||
      r.executive_summary.toLowerCase().includes(q) ||
      (r.pdf_hash && r.pdf_hash.toLowerCase().includes(q)) ||
      r.id.toLowerCase().includes(q)
    )
  })

  const verifiedCount = Object.values(verifyResults).filter((v) => v.status === 'verified').length

  return (
    <div className="space-y-6">
      {/* Tactical Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-[var(--color-border)]">
        <div>
          <div className="flex items-center gap-2">
            <span className="p-1.5 rounded-lg bg-cyan-950/60 border border-cyan-800/40 text-[var(--color-accent)]">
              <FileCheck2 className="w-5 h-5" />
            </span>
            <h1 className="text-xl font-bold tracking-tight text-[var(--color-text-primary)] font-mono uppercase">
              Incident Reports & Forensic Archive
            </h1>
            <Badge variant="telemetry">CHAIN OF CUSTODY SEALED</Badge>
          </div>
          <p className="text-xs font-mono text-[var(--color-text-muted)] mt-1">
            Centrally cataloged forensic PDF dossiers grounded in verified CCTV evidence with SHA-256 byte-level cryptographic integrity.
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <Button
            variant="outline"
            size="sm"
            onClick={loadReports}
            disabled={isLoading}
            className="font-mono text-xs"
          >
            <RotateCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
            Refresh Archive
          </Button>
          <Button size="sm" asChild className="font-mono text-xs">
            <Link to="/investigations">
              <FolderSearch className="w-3.5 h-3.5" />
              Open Investigations
            </Link>
          </Button>
        </div>
      </div>

      {/* Metrics Banner */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="p-4 rounded-xl bg-[var(--color-surface)] border border-[var(--color-border)] flex items-center justify-between">
          <div>
            <p className="text-[10px] font-mono uppercase text-[var(--color-text-muted)] tracking-wider">
              Total Archived Reports
            </p>
            <p className="text-2xl font-bold font-mono text-[var(--color-text-primary)] mt-1">
              {reports.length}
            </p>
          </div>
          <div className="p-2.5 rounded-lg bg-cyan-950/40 border border-cyan-800/30 text-[var(--color-accent)]">
            <FileText className="w-5 h-5" />
          </div>
        </div>

        <div className="p-4 rounded-xl bg-[var(--color-surface)] border border-[var(--color-border)] flex items-center justify-between">
          <div>
            <p className="text-[10px] font-mono uppercase text-[var(--color-text-muted)] tracking-wider">
              SHA-256 Sealed Dossiers
            </p>
            <p className="text-2xl font-bold font-mono text-emerald-400 mt-1">
              {reports.filter((r) => r.pdf_hash).length}
            </p>
          </div>
          <div className="p-2.5 rounded-lg bg-emerald-950/40 border border-emerald-800/30 text-emerald-400">
            <ShieldCheck className="w-5 h-5" />
          </div>
        </div>

        <div className="p-4 rounded-xl bg-[var(--color-surface)] border border-[var(--color-border)] flex items-center justify-between">
          <div>
            <p className="text-[10px] font-mono uppercase text-[var(--color-text-muted)] tracking-wider">
              Audited This Session
            </p>
            <p className="text-2xl font-bold font-mono text-cyan-300 mt-1">
              {verifiedCount}
            </p>
          </div>
          <div className="p-2.5 rounded-lg bg-cyan-950/40 border border-cyan-800/30 text-cyan-300">
            <Lock className="w-5 h-5" />
          </div>
        </div>

        <div className="p-4 rounded-xl bg-[var(--color-surface)] border border-[var(--color-border)] flex items-center justify-between">
          <div>
            <p className="text-[10px] font-mono uppercase text-[var(--color-text-muted)] tracking-wider">
              Forensic Export Spec
            </p>
            <p className="text-base font-bold font-mono text-slate-200 mt-1">
              ISO/IEC 27037
            </p>
          </div>
          <div className="p-2.5 rounded-lg bg-[var(--color-surface-2)] border border-[var(--color-border)] text-slate-300">
            <Layers className="w-5 h-5" />
          </div>
        </div>
      </div>

      {/* Filter & Search Bar */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-3 p-3 rounded-xl bg-[var(--color-surface-2)] border border-[var(--color-border)]">
        <div className="relative w-full sm:w-96">
          <Search className="w-4 h-4 text-[var(--color-text-muted)] absolute left-3 top-2.5" />
          <input
            type="text"
            placeholder="Search reports by title, case name, hash, or UUID..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg pl-9 pr-3 py-1.5 text-xs font-mono text-[var(--color-text-primary)] placeholder:text-[var(--color-text-muted)] focus:outline-none focus:border-[var(--color-accent)]"
          />
        </div>

        <span className="text-xs font-mono text-[var(--color-text-muted)] self-end sm:self-center">
          Showing {filteredReports.length} of {reports.length} report dossiers
        </span>
      </div>

      {/* Reports Dossier List */}
      {isLoading ? (
        <div className="p-12 rounded-xl bg-[var(--color-surface)] border border-[var(--color-border)] flex flex-col items-center justify-center gap-3 text-cyan-400">
          <RotateCw className="w-8 h-8 animate-spin opacity-80" />
          <span className="text-xs font-mono uppercase tracking-widest text-[var(--color-text-secondary)]">
            Loading Cryptographic Reports Archive...
          </span>
        </div>
      ) : filteredReports.length === 0 ? (
        <div className="p-12 rounded-xl bg-[var(--color-surface)] border border-[var(--color-border)] text-center space-y-4 max-w-xl mx-auto">
          <div className="w-12 h-12 rounded-xl bg-cyan-950/60 border border-cyan-800/40 text-[var(--color-accent)] mx-auto flex items-center justify-center">
            <FileText className="w-6 h-6" />
          </div>
          <div className="space-y-1">
            <h3 className="text-base font-bold font-mono text-[var(--color-text-primary)]">
              {reports.length === 0 ? 'No Forensic Reports Generated Yet' : 'No Matching Reports Found'}
            </h3>
            <p className="text-xs text-[var(--color-text-secondary)]">
              {reports.length === 0
                ? 'Incident reports are generated from active cases in the Investigation Workspace, compiling evidence chronology, detector findings, and cryptographic hashes into an official PDF dossier.'
                : 'Try adjusting your search query to locate specific report titles, cases, or cryptographic hashes.'}
            </p>
          </div>
          {reports.length === 0 && (
            <Button size="sm" asChild className="font-mono text-xs">
              <Link to="/investigations">
                <FolderSearch className="w-3.5 h-3.5" />
                Go to Investigations Workspace
              </Link>
            </Button>
          )}
        </div>
      ) : (
        <div className="space-y-4">
          {filteredReports.map((report) => {
            const verification = verifyResults[report.id]
            const isCurrentlyVerifying = isVerifying[report.id]
            const isCurrentlyDownloading = isDownloading[report.id]

            return (
              <div
                key={report.id}
                className="p-5 rounded-xl bg-[var(--color-surface)] border border-[var(--color-border)] hover:border-cyan-800/60 transition-all space-y-4 shadow-sm group"
              >
                {/* Dossier Header */}
                <div className="flex flex-col md:flex-row md:items-start justify-between gap-3">
                  <div className="space-y-1.5 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="p-1 rounded bg-cyan-950/80 text-[var(--color-accent)] border border-cyan-800/40">
                        <FileText className="w-4 h-4" />
                      </span>
                      <h2 className="text-base font-bold font-mono text-[var(--color-text-primary)] group-hover:text-cyan-300 transition-colors">
                        {report.title}
                      </h2>
                      <Badge variant="telemetry">
                        STATUS: {report.status.toUpperCase()}
                      </Badge>
                      {report.pdf_hash && (
                        <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-emerald-950/60 text-emerald-400 border border-emerald-800/40 font-semibold flex items-center gap-1">
                          <ShieldCheck className="w-3 h-3" />
                          SHA-256 SEALED
                        </span>
                      )}
                    </div>

                    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs font-mono text-[var(--color-text-muted)] pt-1">
                      {report.case_title && (
                        <span className="flex items-center gap-1 text-[var(--color-text-secondary)]">
                          <FolderSearch className="w-3.5 h-3.5 text-cyan-400" />
                          Case:{' '}
                          <Link
                            to={`/investigations/${report.investigation_id}`}
                            className="text-[var(--color-accent)] hover:underline font-bold"
                          >
                            {report.case_title}
                          </Link>
                        </span>
                      )}
                      <span className="flex items-center gap-1">
                        <Calendar className="w-3.5 h-3.5" />
                        Generated: {formatDateTime(report.created_at)}
                      </span>
                      <span>Dossier ID: {report.id}</span>
                    </div>
                  </div>

                  {/* Actions: Download & Case Link */}
                  <div className="flex items-center gap-2 shrink-0">
                    <Button
                      variant="outline"
                      size="xs"
                      onClick={() => handleDownload(report)}
                      disabled={isCurrentlyDownloading}
                      className="font-mono text-xs border-cyan-800/40 hover:border-[var(--color-accent)] hover:bg-cyan-950/30 text-cyan-300"
                    >
                      <Download className={`w-3.5 h-3.5 ${isCurrentlyDownloading ? 'animate-bounce' : ''}`} />
                      <span>{isCurrentlyDownloading ? 'Authorizing...' : 'Download PDF'}</span>
                    </Button>

                    <Button variant="ghost" size="xs" asChild className="font-mono text-xs">
                      <Link to={`/investigations/${report.investigation_id}`}>
                        <ExternalLink className="w-3.5 h-3.5" />
                        <span>Open Case</span>
                      </Link>
                    </Button>
                  </div>
                </div>

                {/* Executive Summary */}
                {report.executive_summary && (
                  <div className="p-3 rounded-lg bg-[var(--color-surface-2)] border border-[var(--color-border)] text-xs text-[var(--color-text-secondary)] leading-relaxed font-sans">
                    <span className="font-mono text-[10px] uppercase font-bold text-[var(--color-text-muted)] block mb-1">
                      Executive Summary & Evidentiary Findings:
                    </span>
                    {report.executive_summary}
                  </div>
                )}

                {/* Cryptographic Proof & Verification Box */}
                <div className="pt-2 border-t border-[var(--color-border)] flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs font-mono">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-[10px] text-[var(--color-text-muted)] uppercase">
                      Integrity Digest:
                    </span>
                    {report.pdf_hash ? (
                      <code className="px-2 py-0.5 rounded bg-black/60 border border-[var(--color-border)] text-[11px] text-cyan-300 font-mono select-all">
                        {report.pdf_hash}
                      </code>
                    ) : (
                      <span className="text-[var(--color-text-muted)] text-[11px]">Uncalculated</span>
                    )}

                    {/* Live Verification Badge if checked */}
                    {verification && (
                      <span
                        className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold ${
                          verification.status === 'verified'
                            ? 'bg-emerald-950 text-emerald-300 border border-emerald-600/50'
                            : 'bg-rose-950 text-rose-300 border border-rose-600/50'
                        }`}
                      >
                        {verification.status === 'verified' ? (
                          <>
                            <CheckCircle2 className="w-3 h-3" />
                            INTACT ({(verification.hash_algorithm || 'SHA256').toUpperCase()})
                          </>
                        ) : (
                          <>
                            <AlertTriangle className="w-3 h-3" />
                            HASH MISMATCH
                          </>
                        )}
                      </span>
                    )}
                  </div>

                  <Button
                    variant="ghost"
                    size="xs"
                    onClick={() => handleVerify(report.investigation_id, report.id)}
                    disabled={isCurrentlyVerifying}
                    className="font-mono text-[11px] text-[var(--color-text-secondary)] hover:text-white"
                  >
                    <RotateCw className={`w-3 h-3 mr-1 ${isCurrentlyVerifying ? 'animate-spin text-cyan-400' : ''}`} />
                    <span>{isCurrentlyVerifying ? 'Hashing...' : 'Verify Cryptographic Hash'}</span>
                  </Button>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
