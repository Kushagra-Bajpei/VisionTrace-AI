/**
 * Case Workspace Page (Phase 7).
 * Tactical investigation environment for assembling evidentiary timelines,
 * taking investigator notes, verifying detector/similarity metrics,
 * playing video evidence at exact timestamps, and generating audit-grade forensic PDF reports.
 */
import { useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  ArrowLeft,
  Calendar,
  Check,
  ChevronDown,
  Clock,
  Download,
  Edit2,
  FileCheck2,
  FileText,
  FileVideo,
  Film,
  Layers,
  MessageSquare,
  Play,
  Plus,
  RotateCw,
  Save,
  Send,
  Shield,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Trash2,
  User,
  X,
} from 'lucide-react'
import { Card, CardContent } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Modal } from '@/components/ui/Modal'
import { Spinner } from '@/components/ui/Loading'
import { VideoPlayerModal } from '@/components/video/VideoPlayerModal'
import { investigationService } from '@/services/investigation'
import { videoService } from '@/services/video'
import { authService } from '@/services/auth'
import { useAuth } from '@/context/AuthContext'
import { formatDateTime, formatDuration } from '@/lib/utils'
import type {
  CasePriority,
  CaseReport,
  CaseStatus,
  IntegrityVerificationResult,
  InvestigationCase,
  InvestigationEvidence,
  Video,
} from '@/types'

export function CaseWorkspacePage() {
  const { caseId } = useParams<{ caseId: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { canEditCase, canDeleteCase } = useAuth()

  // State
  const [activeTab, setActiveTab] = useState<'timeline' | 'notes' | 'reports'>('timeline')
  const [editingTitle, setEditingTitle] = useState(false)
  const [titleInput, setTitleInput] = useState('')
  const [isReportModalOpen, setIsReportModalOpen] = useState(false)
  const [reportTitle, setReportTitle] = useState('')
  const [reportSummary, setReportSummary] = useState('')
  const [reportNotes, setReportNotes] = useState('')
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false)

  // Evidence editing state
  const [editingEvidenceId, setEditingEvidenceId] = useState<string | null>(null)
  const [evidenceNoteInput, setEvidenceNoteInput] = useState<string>('')

  // Quick note input
  const [quickNote, setQuickNote] = useState('')

  // Cryptographic integrity verification state
  const [integrityResults, setIntegrityResults] = useState<Record<string, IntegrityVerificationResult>>({})
  const [verifyingId, setVerifyingId] = useState<string | null>(null)

  const handleVerifyEvidence = async (evidenceId: string) => {
    if (!caseId) return
    setVerifyingId(evidenceId)
    try {
      const res = await authService.verifyEvidenceIntegrity(caseId, evidenceId)
      setIntegrityResults((prev) => ({ ...prev, [evidenceId]: res }))
    } catch {
      //
    } finally {
      setVerifyingId(null)
    }
  }

  const handleVerifyReport = async (reportId: string) => {
    if (!caseId) return
    setVerifyingId(reportId)
    try {
      const res = await authService.verifyReportIntegrity(caseId, reportId)
      setIntegrityResults((prev) => ({ ...prev, [reportId]: res }))
    } catch {
      //
    } finally {
      setVerifyingId(null)
    }
  }

  const handleDownloadReportWithToken = async (reportId: string, downloadUrl: string) => {
    try {
      const mediaToken = await authService.getMediaToken('report', reportId)
      const secureUrl = `${downloadUrl}?media_token=${encodeURIComponent(mediaToken)}`
      window.open(secureUrl, '_blank')
    } catch {
      window.open(downloadUrl, '_blank')
    }
  }

  // Video Player Modal state for "View Evidence"
  const [playerVideo, setPlayerVideo] = useState<Video | null>(null)
  const [playerTimestamp, setPlayerTimestamp] = useState<number | null>(null)
  const [isPlayerOpen, setIsPlayerOpen] = useState(false)
  const [isLoadingPlayerVideo, setIsLoadingPlayerVideo] = useState(false)

  // Fetch Case Detail
  const {
    data: caseData,
    isLoading,
    isError,
    refetch,
  } = useQuery({
    queryKey: ['case', caseId],
    queryFn: () => investigationService.getCase(caseId!),
    enabled: Boolean(caseId),
  })

  // Fetch Reports
  const { data: reports = [], refetch: refetchReports } = useQuery({
    queryKey: ['case-reports', caseId],
    queryFn: () => investigationService.listReports(caseId!),
    enabled: Boolean(caseId),
  })

  // Mutations
  const updateCaseMutation = useMutation({
    mutationFn: (payload: { title?: string; description?: string; status?: CaseStatus; priority?: CasePriority }) =>
      investigationService.updateCase(caseId!, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['case', caseId] })
      queryClient.invalidateQueries({ queryKey: ['cases'] })
      setEditingTitle(false)
    },
  })

  const deleteCaseMutation = useMutation({
    mutationFn: () => investigationService.deleteCase(caseId!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['cases'] })
      navigate('/investigations')
    },
  })

  const updateEvidenceMutation = useMutation({
    mutationFn: ({ evidenceId, notes }: { evidenceId: string; notes: string }) =>
      investigationService.updateEvidence(caseId!, evidenceId, { notes }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['case', caseId] })
      setEditingEvidenceId(null)
    },
  })

  const deleteEvidenceMutation = useMutation({
    mutationFn: (evidenceId: string) => investigationService.deleteEvidence(caseId!, evidenceId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['case', caseId] })
      queryClient.invalidateQueries({ queryKey: ['cases'] })
    },
  })

  const addNoteMutation = useMutation({
    mutationFn: (message: string) =>
      investigationService.addCaseNote(caseId!, { message, sender_type: 'investigator' }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['case', caseId] })
      setQuickNote('')
    },
  })

  const generateReportMutation = useMutation({
    mutationFn: () =>
      investigationService.generateReport(caseId!, {
        title: reportTitle.trim() || undefined,
        executive_summary: reportSummary.trim() || undefined,
        custom_notes: reportNotes.trim() || undefined,
        include_evidence_thumbnails: true,
      }),
    onSuccess: (report) => {
      queryClient.invalidateQueries({ queryKey: ['case-reports', caseId] })
      setIsReportModalOpen(false)
      setActiveTab('reports')
      if (report.download_url) {
        window.open(report.download_url, '_blank')
      }
    },
  })

  // Handlers
  const handleOpenPlayer = async (item: InvestigationEvidence) => {
    setIsLoadingPlayerVideo(true)
    try {
      const vid = await videoService.getVideo(item.video_id)
      setPlayerVideo(vid)
      setPlayerTimestamp(item.timestamp)
      setIsPlayerOpen(true)
    } catch (e) {
      console.error('Failed to load video for playback:', e)
    } finally {
      setIsLoadingPlayerVideo(false)
    }
  }

  const handleStartEditNote = (item: InvestigationEvidence) => {
    setEditingEvidenceId(item.id)
    setEvidenceNoteInput(item.notes || '')
  }

  const handleSaveNote = (evidenceId: string) => {
    updateEvidenceMutation.mutate({ evidenceId, notes: evidenceNoteInput })
  }

  const handleQuickNoteSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!quickNote.trim()) return
    addNoteMutation.mutate(quickNote.trim())
  }

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center py-28 text-center gap-3">
        <Spinner className="w-8 h-8 text-[var(--color-accent)]" />
        <p className="text-xs text-[var(--color-text-muted)] font-mono">LOADING EVIDENTIARY DOSSIER...</p>
      </div>
    )
  }

  if (isError || !caseData) {
    return (
      <div className="max-w-md mx-auto py-20 text-center space-y-4">
        <ShieldAlert className="w-12 h-12 text-red-400 mx-auto" />
        <h2 className="text-base font-bold text-[var(--color-text-primary)]">Investigation Case Not Found</h2>
        <p className="text-xs text-[var(--color-text-secondary)]">
          The requested case identifier may have been deleted or does not exist.
        </p>
        <Button variant="outline" size="sm" onClick={() => navigate('/investigations')}>
          <ArrowLeft className="w-3.5 h-3.5 mr-1.5" />
          Back to Investigations
        </Button>
      </div>
    )
  }

  const evidenceItems = caseData.evidence_items || []
  const messages = caseData.messages || []

  return (
    <div className="space-y-6">
      {/* ── Top Bar ── */}
      <div className="flex flex-col gap-4">
        <div className="flex items-center justify-between gap-3">
          <Link
            to="/investigations"
            className="inline-flex items-center text-xs text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)] transition-colors font-mono"
          >
            <ArrowLeft className="w-3.5 h-3.5 mr-1" />
            ALL CASES
          </Link>

          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setIsReportModalOpen(true)}
              className="border-[var(--color-accent)] text-[var(--color-accent)] hover:bg-[var(--color-surface-2)] text-xs font-semibold shadow-[0_0_15px_rgba(0,229,255,0.1)]"
            >
              <FileCheck2 className="w-4 h-4 mr-1.5" />
              Generate Forensic PDF
            </Button>

            {canDeleteCase(caseData) && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setIsDeleteModalOpen(true)}
                className="text-red-400 hover:text-red-300 hover:bg-red-950/20 text-xs"
              >
                <Trash2 className="w-3.5 h-3.5 mr-1" />
                Delete Case
              </Button>
            )}
          </div>
        </div>

        {/* ── Case Header Card ── */}
        <Card className="border-[var(--color-border)] bg-[var(--color-surface-1)]">
          <CardContent className="p-5 space-y-4">
            {/* Title & Status Bar */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
              <div className="flex-1">
                {editingTitle ? (
                  <div className="flex items-center gap-2 max-w-lg">
                    <input
                      type="text"
                      value={titleInput}
                      onChange={(e) => setTitleInput(e.target.value)}
                      className="flex-1 bg-[var(--color-surface-2)] border border-[var(--color-accent)] rounded px-2.5 py-1 text-base font-bold text-[var(--color-text-primary)] focus:outline-none"
                    />
                    <Button
                      size="sm"
                      variant="primary"
                      onClick={() => updateCaseMutation.mutate({ title: titleInput.trim() })}
                      className="bg-[var(--color-accent)] text-black"
                    >
                      <Check className="w-3.5 h-3.5" />
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => setEditingTitle(false)}
                    >
                      <X className="w-3.5 h-3.5" />
                    </Button>
                  </div>
                ) : (
                  <div className="flex items-center gap-2.5">
                    <h1 className="text-xl font-bold tracking-tight text-[var(--color-text-primary)]">
                      {caseData.title}
                    </h1>
                    <button
                      onClick={() => {
                        setTitleInput(caseData.title)
                        setEditingTitle(true)
                      }}
                      className="text-[var(--color-text-muted)] hover:text-[var(--color-accent)] transition-colors p-1"
                      title="Edit Case Title"
                    >
                      <Edit2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                )}
                <p className="text-xs text-[var(--color-text-secondary)] mt-1">
                  {caseData.description || 'No formal briefing documented. Add observations below.'}
                </p>
              </div>

              {/* Status and Priority Selectors */}
              <div className="flex items-center gap-2 shrink-0">
                <div className="flex items-center gap-1.5 bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-lg px-2.5 py-1">
                  <span className="text-[10px] uppercase font-mono text-[var(--color-text-muted)]">STATUS:</span>
                  <select
                    value={caseData.status}
                    onChange={(e) => updateCaseMutation.mutate({ status: e.target.value as CaseStatus })}
                    className="bg-transparent text-xs font-semibold text-[var(--color-text-primary)] focus:outline-none cursor-pointer"
                  >
                    <option value="open">OPEN</option>
                    <option value="in_progress">IN PROGRESS</option>
                    <option value="under_review">UNDER REVIEW</option>
                    <option value="closed">CLOSED</option>
                  </select>
                </div>

                <div className="flex items-center gap-1.5 bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-lg px-2.5 py-1">
                  <span className="text-[10px] uppercase font-mono text-[var(--color-text-muted)]">PRIORITY:</span>
                  <select
                    value={caseData.priority}
                    onChange={(e) => updateCaseMutation.mutate({ priority: e.target.value as CasePriority })}
                    className="bg-transparent text-xs font-semibold text-[var(--color-text-primary)] focus:outline-none cursor-pointer"
                  >
                    <option value="low">LOW</option>
                    <option value="medium">MEDIUM</option>
                    <option value="high">HIGH</option>
                    <option value="critical">CRITICAL</option>
                  </select>
                </div>
              </div>
            </div>

            {/* Meta telemetry row */}
            <div className="flex flex-wrap items-center gap-y-2 gap-x-5 pt-3 border-t border-[var(--color-border)] text-xs font-mono text-[var(--color-text-muted)]">
              <div className="flex items-center gap-1.5">
                <span className="text-[var(--color-text-secondary)]">CASE ID:</span>
                <span className="text-[var(--color-text-primary)]">{caseData.id.slice(0, 18)}...</span>
              </div>
              <div className="flex items-center gap-1.5">
                <Layers className="w-3.5 h-3.5 text-[var(--color-accent)]" />
                <span className="text-[var(--color-text-primary)]">{evidenceItems.length}</span> EVIDENCE ITEMS
              </div>
              <div className="flex items-center gap-1.5">
                <MessageSquare className="w-3.5 h-3.5 text-[var(--color-accent)]" />
                <span className="text-[var(--color-text-primary)]">{messages.length}</span> LOG NOTES
              </div>
              <div className="flex items-center gap-1.5">
                <Clock className="w-3.5 h-3.5" />
                CREATED: {formatDateTime(caseData.created_at)}
              </div>
              {caseData.tags && caseData.tags.length > 0 && (
                <div className="flex items-center gap-1">
                  {caseData.tags.map((t) => (
                    <span key={t} className="px-1.5 py-0.5 rounded bg-[var(--color-surface-2)] text-[10px] text-[var(--color-text-secondary)] border border-[var(--color-border)]">
                      #{t}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* ── Navigation Tabs ── */}
      <div className="border-b border-[var(--color-border)] flex items-center justify-between">
        <div className="flex items-center gap-4">
          <button
            onClick={() => setActiveTab('timeline')}
            className={`pb-3 text-xs font-bold tracking-wider uppercase transition-colors relative flex items-center gap-2 ${
              activeTab === 'timeline'
                ? 'text-[var(--color-accent)]'
                : 'text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)]'
            }`}
          >
            <Layers className="w-4 h-4" />
            Evidentiary Timeline ({evidenceItems.length})
            {activeTab === 'timeline' && (
              <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-[var(--color-accent)] shadow-[0_0_8px_var(--color-accent)]" />
            )}
          </button>

          <button
            onClick={() => setActiveTab('notes')}
            className={`pb-3 text-xs font-bold tracking-wider uppercase transition-colors relative flex items-center gap-2 ${
              activeTab === 'notes'
                ? 'text-[var(--color-accent)]'
                : 'text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)]'
            }`}
          >
            <MessageSquare className="w-4 h-4" />
            Investigation Notes & Audit ({messages.length})
            {activeTab === 'notes' && (
              <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-[var(--color-accent)] shadow-[0_0_8px_var(--color-accent)]" />
            )}
          </button>

          <button
            onClick={() => setActiveTab('reports')}
            className={`pb-3 text-xs font-bold tracking-wider uppercase transition-colors relative flex items-center gap-2 ${
              activeTab === 'reports'
                ? 'text-[var(--color-accent)]'
                : 'text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)]'
            }`}
          >
            <FileText className="w-4 h-4" />
            Generated Reports ({reports.length})
            {activeTab === 'reports' && (
              <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-[var(--color-accent)] shadow-[0_0_8px_var(--color-accent)]" />
            )}
          </button>
        </div>

        <Link
          to="/search"
          className="pb-3 text-xs font-mono text-[var(--color-accent)] hover:underline inline-flex items-center gap-1"
        >
          <Plus className="w-3.5 h-3.5" />
          SEARCH EVIDENCE TO ADD
        </Link>
      </div>

      {/* ── TAB 1: EVIDENTIARY TIMELINE ── */}
      {activeTab === 'timeline' && (
        <div className="space-y-4">
          {evidenceItems.length === 0 ? (
            <Card className="border-[var(--color-border)] bg-[var(--color-surface-1)]">
              <CardContent className="py-16 text-center space-y-3">
                <div className="w-12 h-12 rounded-xl bg-[var(--color-surface-2)] border border-[var(--color-border)] flex items-center justify-center mx-auto text-[var(--color-text-muted)]">
                  <Film className="w-6 h-6" />
                </div>
                <h3 className="text-sm font-semibold text-[var(--color-text-primary)]">
                  No evidence items linked yet
                </h3>
                <p className="text-xs text-[var(--color-text-muted)] max-w-sm mx-auto">
                  Search surveillance footage using natural language or visual similarity in the AI Search tab, then click &ldquo;Add to Case&rdquo; to attach timestamped clips and crops.
                </p>
                <Link to="/search">
                  <Button variant="outline" size="sm" className="text-xs mt-2 border-[var(--color-border)]">
                    <Sparkles className="w-3.5 h-3.5 mr-1.5 text-[var(--color-accent)]" />
                    Open AI Surveillance Search
                  </Button>
                </Link>
              </CardContent>
            </Card>
          ) : (
            <div className="relative pl-6 space-y-4 before:content-[''] before:absolute before:left-2 before:top-3 before:bottom-3 before:w-0.5 before:bg-[var(--color-border)]">
              {evidenceItems.map((item: InvestigationEvidence, index: number) => {
                const isEditingNote = editingEvidenceId === item.id

                return (
                  <div key={item.id} className="relative group">
                    {/* Timeline Node dot */}
                    <div className="absolute -left-6 top-5 w-4 h-4 rounded-full bg-[var(--color-surface-1)] border-2 border-[var(--color-accent)] flex items-center justify-center">
                      <div className="w-1.5 h-1.5 rounded-full bg-[var(--color-accent)]" />
                    </div>

                    <Card className="border-[var(--color-border)] bg-[var(--color-surface-1)] hover:border-[var(--color-border-accent)] transition-all">
                      <CardContent className="p-4 space-y-3">
                        {/* Top row: Sequence, Timestamp, Source video */}
                        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                          <div className="flex items-center gap-2">
                            <span className="font-mono text-xs px-2 py-0.5 rounded bg-[var(--color-surface-2)] text-[var(--color-text-primary)] font-bold border border-[var(--color-border)]">
                              #{item.sequence_number || index + 1}
                            </span>
                            <span className="font-mono text-xs text-[var(--color-accent)] font-semibold flex items-center gap-1">
                              <Clock className="w-3.5 h-3.5" />
                              {formatDuration(item.timestamp)} ({item.timestamp.toFixed(1)}s)
                            </span>
                            <Badge variant="default" className="uppercase font-mono text-[10px]">
                              {item.evidence_type.replace('_', ' ')}
                            </Badge>
                          </div>

                          <div className="flex items-center gap-2 text-xs font-mono text-[var(--color-text-muted)]">
                            <FileVideo className="w-3.5 h-3.5 text-[var(--color-text-secondary)]" />
                            <span className="truncate max-w-[200px]" title={item.video_title || item.video_filename || item.video_id}>
                              {item.video_title || item.video_filename || item.video_id}
                            </span>
                          </div>
                        </div>

                        {/* Middle row: Visual Preview & Metrics */}
                        <div className="flex flex-col sm:flex-row gap-4">
                          {/* Visual thumbnail / crop */}
                          <div className="w-full sm:w-44 h-28 rounded-lg bg-[var(--color-surface-2)] border border-[var(--color-border)] overflow-hidden shrink-0 relative flex items-center justify-center">
                            {item.crop_url ? (
                              <img
                                src={item.crop_url}
                                alt="Detection crop"
                                className="w-full h-full object-contain bg-black/40"
                              />
                            ) : item.frame_url ? (
                              <img
                                src={item.frame_url}
                                alt="Frame preview"
                                className="w-full h-full object-cover"
                              />
                            ) : (
                              <div className="flex flex-col items-center justify-center text-center p-2 text-[var(--color-text-muted)] text-[10px] font-mono">
                                <Film className="w-5 h-5 mb-1" />
                                NO VISUAL ARCHIVE
                              </div>
                            )}

                            {/* Evidence Badge Overlay */}
                            {item.object_class && (
                              <div className="absolute bottom-1.5 left-1.5 px-1.5 py-0.5 rounded bg-black/80 backdrop-blur-sm border border-white/10 text-[10px] font-mono text-[var(--color-accent)]">
                                {item.object_class}
                              </div>
                            )}
                          </div>

                          {/* Technical Metrics & Investigator Observation */}
                          <div className="flex-1 space-y-2.5">
                            {/* Metric Badges */}
                            <div className="flex flex-wrap items-center gap-2">
                              {item.confidence !== null && item.confidence !== undefined && (
                                <div className="flex items-center gap-1 px-2 py-1 rounded bg-[var(--color-surface-2)] border border-[var(--color-border)] text-xs font-mono">
                                  <span className="text-[var(--color-text-muted)]">DETECTOR CONF:</span>
                                  <span className="text-emerald-400 font-bold">
                                    {(item.confidence * 100).toFixed(1)}%
                                  </span>
                                  <span className="text-[10px] text-[var(--color-text-muted)]">(YOLOv8)</span>
                                </div>
                              )}

                              {item.visual_similarity_score !== null && item.visual_similarity_score !== undefined && (
                                <div className="flex items-center gap-1 px-2 py-1 rounded bg-[var(--color-surface-2)] border border-[var(--color-border-accent)] text-xs font-mono">
                                  <span className="text-[var(--color-accent)]">VISUAL SIMILARITY:</span>
                                  <span className="text-[var(--color-accent)] font-bold">
                                    {(item.visual_similarity_score * 100).toFixed(1)}%
                                  </span>
                                  <span className="text-[10px] text-[var(--color-text-muted)]">(OpenCLIP)</span>
                                </div>
                              )}
                            </div>

                            {/* Notes container */}
                            <div className="rounded-lg bg-[var(--color-surface-2)]/60 border border-[var(--color-border)] p-2.5 text-xs">
                              <div className="flex items-center justify-between mb-1">
                                <span className="font-semibold text-[var(--color-text-secondary)] text-[11px] uppercase tracking-wider">
                                  Investigator Observation
                                </span>
                                {!isEditingNote && (
                                  <button
                                    onClick={() => handleStartEditNote(item)}
                                    className="text-[var(--color-text-muted)] hover:text-[var(--color-accent)] p-0.5 transition-colors"
                                    title="Edit Note"
                                  >
                                    <Edit2 className="w-3 h-3" />
                                  </button>
                                )}
                              </div>

                              {isEditingNote ? (
                                <div className="space-y-2 mt-1">
                                  <textarea
                                    rows={2}
                                    value={evidenceNoteInput}
                                    onChange={(e) => setEvidenceNoteInput(e.target.value)}
                                    className="w-full bg-[var(--color-surface-1)] border border-[var(--color-accent)] rounded p-2 text-xs text-[var(--color-text-primary)] focus:outline-none resize-none"
                                    placeholder="Enter forensic observations, suspect clothing, movements..."
                                  />
                                  <div className="flex items-center justify-end gap-1.5">
                                    <Button
                                      size="sm"
                                      variant="ghost"
                                      onClick={() => setEditingEvidenceId(null)}
                                      className="h-6 text-[11px]"
                                    >
                                      Cancel
                                    </Button>
                                    <Button
                                      size="sm"
                                      variant="primary"
                                      onClick={() => handleSaveNote(item.id)}
                                      disabled={updateEvidenceMutation.isPending}
                                      className="h-6 text-[11px] bg-[var(--color-accent)] text-black"
                                    >
                                      <Save className="w-3 h-3 mr-1" />
                                      Save Note
                                    </Button>
                                  </div>
                                </div>
                              ) : (
                                <p className="text-[var(--color-text-secondary)] italic">
                                  {item.notes || 'No manual notes recorded for this evidence item.'}
                                </p>
                              )}
                            </div>
                          </div>
                        </div>

                        {/* Bottom action row */}
                        <div className="pt-2 border-t border-[var(--color-border)] flex flex-wrap items-center justify-between gap-2">
                          <div className="flex items-center gap-2">
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => handleOpenPlayer(item)}
                              disabled={isLoadingPlayerVideo}
                              className="border-[var(--color-border)] text-xs font-semibold hover:border-[var(--color-accent)] hover:text-[var(--color-accent)]"
                            >
                              <Play className="w-3.5 h-3.5 mr-1.5 fill-current" />
                              View Evidence in Video ({item.timestamp.toFixed(1)}s)
                            </Button>

                            {/* Cryptographic SHA-256 Integrity */}
                            {integrityResults[item.id] ? (
                              <span
                                className={`inline-flex items-center gap-1 text-[11px] font-mono px-2 py-0.5 rounded border ${
                                  integrityResults[item.id].status === 'verified'
                                    ? 'bg-emerald-950/60 text-emerald-400 border-emerald-500/40'
                                    : integrityResults[item.id].status === 'mismatch'
                                    ? 'bg-red-950/60 text-red-400 border-red-500/40'
                                    : 'bg-amber-950/60 text-amber-400 border-amber-500/40'
                                }`}
                              >
                                <ShieldCheck className="w-3 h-3" />
                                {integrityResults[item.id].status.toUpperCase()}
                              </span>
                            ) : item.evidence_hash ? (
                              <Button
                                variant="ghost"
                                size="xs"
                                onClick={() => handleVerifyEvidence(item.id)}
                                disabled={verifyingId === item.id}
                                className="text-[11px] font-mono text-cyan-400 hover:text-cyan-300 hover:bg-cyan-950/30"
                              >
                                <ShieldCheck className={`w-3 h-3 mr-1 ${verifyingId === item.id ? 'animate-spin' : ''}`} />
                                Verify SHA-256
                              </Button>
                            ) : null}
                          </div>

                          {canEditCase(caseData) && (
                            <button
                              onClick={() => deleteEvidenceMutation.mutate(item.id)}
                              disabled={deleteEvidenceMutation.isPending}
                              className="text-xs text-red-400 hover:text-red-300 transition-colors p-1"
                              title="Remove evidence item from case"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          )}
                        </div>
                      </CardContent>
                    </Card>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      )}

      {/* ── TAB 2: INVESTIGATION NOTES & AUDIT LOG ── */}
      {activeTab === 'notes' && (
        <div className="space-y-4 max-w-3xl">
          {/* Quick Note Input */}
          <Card className="border-[var(--color-border)] bg-[var(--color-surface-1)]">
            <CardContent className="p-4">
              <form onSubmit={handleQuickNoteSubmit} className="space-y-2">
                <label className="block text-xs font-semibold uppercase tracking-wider text-[var(--color-text-secondary)]">
                  Add Case Log Entry / Investigator Note
                </label>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={quickNote}
                    onChange={(e) => setQuickNote(e.target.value)}
                    placeholder="e.g. Dispatched security team to check gate perimeter locks..."
                    className="flex-1 bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-lg px-3 py-2 text-xs text-[var(--color-text-primary)] placeholder-[var(--color-text-muted)] focus:outline-none focus:border-[var(--color-accent)]"
                  />
                  <Button
                    type="submit"
                    variant="primary"
                    size="sm"
                    disabled={!quickNote.trim() || addNoteMutation.isPending}
                    className="bg-[var(--color-accent)] text-black font-semibold shrink-0"
                  >
                    <Send className="w-3.5 h-3.5 mr-1.5" />
                    Record Note
                  </Button>
                </div>
              </form>
            </CardContent>
          </Card>

          {/* Messages list */}
          {messages.length === 0 ? (
            <div className="text-center py-12 text-xs text-[var(--color-text-muted)] font-mono">
              NO INVESTIGATION LOG ENTRIES RECORDED YET.
            </div>
          ) : (
            <div className="space-y-2">
              {messages.map((msg) => (
                <div
                  key={msg.id}
                  className="p-3 rounded-lg bg-[var(--color-surface-1)] border border-[var(--color-border)] flex items-start gap-3"
                >
                  <div className="w-7 h-7 rounded-full bg-[var(--color-surface-2)] border border-[var(--color-border)] flex items-center justify-center shrink-0 text-[var(--color-accent)]">
                    <User className="w-3.5 h-3.5" />
                  </div>
                  <div className="flex-1 space-y-1">
                    <div className="flex items-center justify-between text-[11px] font-mono">
                      <span className="font-semibold text-[var(--color-text-primary)] uppercase">
                        {msg.sender_type}
                      </span>
                      <span className="text-[var(--color-text-muted)]">{formatDateTime(msg.created_at)}</span>
                    </div>
                    <p className="text-xs text-[var(--color-text-secondary)] leading-relaxed">
                      {msg.message}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ── TAB 3: GENERATED REPORTS ── */}
      {activeTab === 'reports' && (
        <div className="space-y-4 max-w-4xl">
          <div className="flex items-center justify-between">
            <p className="text-xs text-[var(--color-text-muted)]">
              Forensic PDF investigation reports compiled for authorized judicial, audit, or enterprise security use.
            </p>
            <Button
              variant="primary"
              size="sm"
              onClick={() => setIsReportModalOpen(true)}
              className="bg-[var(--color-accent)] text-black font-semibold text-xs"
            >
              <FileCheck2 className="w-3.5 h-3.5 mr-1.5" />
              Compile New Report
            </Button>
          </div>

          {reports.length === 0 ? (
            <Card className="border-[var(--color-border)] bg-[var(--color-surface-1)]">
              <CardContent className="py-14 text-center space-y-3">
                <FileText className="w-8 h-8 text-[var(--color-text-muted)] mx-auto" />
                <h4 className="text-sm font-semibold text-[var(--color-text-primary)]">
                  No forensic reports generated yet
                </h4>
                <p className="text-xs text-[var(--color-text-muted)] max-w-xs mx-auto">
                  Click &ldquo;Compile New Report&rdquo; to build an audit-grade multi-page PDF dossier with chronological evidence and model limitations.
                </p>
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-3">
              {reports.map((report: CaseReport) => (
                <Card key={report.id} className="border-[var(--color-border)] bg-[var(--color-surface-1)]">
                  <CardContent className="p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <Badge variant="success" className="uppercase font-mono text-[10px]">
                          {report.status}
                        </Badge>
                        <h4 className="text-sm font-bold text-[var(--color-text-primary)]">
                          {report.title}
                        </h4>
                      </div>
                      <p className="text-xs text-[var(--color-text-secondary)] line-clamp-1">
                        {report.executive_summary}
                      </p>
                      <div className="text-[10px] font-mono text-[var(--color-text-muted)]">
                        REPORT ID: {report.id} | COMPILED: {formatDateTime(report.created_at)}
                      </div>
                    </div>

                    <div className="flex flex-wrap items-center gap-2 shrink-0">
                      {/* Report SHA-256 Integrity */}
                      {integrityResults[report.id] ? (
                        <span
                          className={`inline-flex items-center gap-1 text-[11px] font-mono px-2 py-0.5 rounded border ${
                            integrityResults[report.id].status === 'verified'
                              ? 'bg-emerald-950/60 text-emerald-400 border-emerald-500/40'
                              : 'bg-red-950/60 text-red-400 border-red-500/40'
                          }`}
                        >
                          <ShieldCheck className="w-3 h-3" />
                          {integrityResults[report.id].status.toUpperCase()}
                        </span>
                      ) : (
                        <Button
                          variant="ghost"
                          size="xs"
                          onClick={() => handleVerifyReport(report.id)}
                          disabled={verifyingId === report.id}
                          className="text-[11px] font-mono text-cyan-400 hover:text-cyan-300 hover:bg-cyan-950/30"
                        >
                          <ShieldCheck className={`w-3 h-3 mr-1 ${verifyingId === report.id ? 'animate-spin' : ''}`} />
                          Verify SHA-256
                        </Button>
                      )}

                      {report.download_url && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleDownloadReportWithToken(report.id, report.download_url!)}
                          className="text-xs border-[var(--color-accent)] text-[var(--color-accent)] hover:bg-[var(--color-surface-2)] cursor-pointer"
                        >
                          <Download className="w-3.5 h-3.5 mr-1.5" />
                          Download PDF
                        </Button>
                      )}
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ── Generate Report Modal ── */}
      <Modal
        isOpen={isReportModalOpen}
        onClose={() => setIsReportModalOpen(false)}
        title="Generate Forensic Investigation Dossier (PDF)"
      >
        <div className="space-y-4">
          <p className="text-xs text-[var(--color-text-secondary)]">
            Generates a printable, audit-grade incident report including executive briefing,
            all {evidenceItems.length} chronological evidence milestones, embedded crops/keyframes,
            and legal/scientific disclaimers regarding detector uncertainty and visual similarity rankings.
          </p>

          <div>
            <label className="block text-xs font-medium text-[var(--color-text-secondary)] mb-1">
              Report Title
            </label>
            <input
              type="text"
              placeholder={`Forensic Incident Dossier: ${caseData.title}`}
              value={reportTitle}
              onChange={(e) => setReportTitle(e.target.value)}
              className="w-full bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-lg px-3 py-2 text-xs text-[var(--color-text-primary)] placeholder-[var(--color-text-muted)] focus:outline-none focus:border-[var(--color-accent)]"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-[var(--color-text-secondary)] mb-1">
              Custom Executive Briefing (Optional)
            </label>
            <textarea
              rows={3}
              placeholder="Leave blank to use auto-generated case briefing summary..."
              value={reportSummary}
              onChange={(e) => setReportSummary(e.target.value)}
              className="w-full bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-lg px-3 py-2 text-xs text-[var(--color-text-primary)] placeholder-[var(--color-text-muted)] focus:outline-none focus:border-[var(--color-accent)] resize-none"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-[var(--color-text-secondary)] mb-1">
              Investigator Addendum / Concluding Remarks (Optional)
            </label>
            <textarea
              rows={2}
              placeholder="e.g. Handed over to local law enforcement with full chain-of-custody checksums..."
              value={reportNotes}
              onChange={(e) => setReportNotes(e.target.value)}
              className="w-full bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-lg px-3 py-2 text-xs text-[var(--color-text-primary)] placeholder-[var(--color-text-muted)] focus:outline-none focus:border-[var(--color-accent)] resize-none"
            />
          </div>

          <div className="p-3 rounded-lg bg-[var(--color-surface-2)] border border-[var(--color-border)] text-[11px] text-[var(--color-text-muted)] space-y-1">
            <div className="font-semibold text-[var(--color-text-secondary)] flex items-center gap-1.5">
              <Shield className="w-3.5 h-3.5 text-[var(--color-accent)]" />
              FORENSIC INTEGRITY STANDARDS
            </div>
            <p>
              Embedded image crops are rendered at high resolution from preserved local evidence directories.
              Detections and visual similarities are explicitly flagged as algorithmic estimations.
            </p>
          </div>

          <div className="flex items-center justify-end gap-2 pt-3 border-t border-[var(--color-border)]">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setIsReportModalOpen(false)}
            >
              Cancel
            </Button>
            <Button
              variant="primary"
              size="sm"
              onClick={() => generateReportMutation.mutate()}
              disabled={generateReportMutation.isPending}
              className="bg-[var(--color-accent)] text-black font-semibold hover:bg-[var(--color-accent-hover)]"
            >
              {generateReportMutation.isPending ? (
                <>
                  <Spinner className="w-3.5 h-3.5 mr-1.5" />
                  Generating PDF...
                </>
              ) : (
                <>
                  <Download className="w-3.5 h-3.5 mr-1.5" />
                  Build & Download PDF
                </>
              )}
            </Button>
          </div>
        </div>
      </Modal>

      {/* ── Delete Confirmation Modal ── */}
      <Modal
        isOpen={isDeleteModalOpen}
        onClose={() => setIsDeleteModalOpen(false)}
        title="Delete Investigation Case"
      >
        <div className="space-y-4">
          <p className="text-xs text-[var(--color-text-secondary)]">
            Are you sure you want to permanently delete <strong className="text-white">&ldquo;{caseData.title}&rdquo;</strong>?
          </p>
          <div className="p-3 rounded-lg bg-amber-950/20 border border-amber-900/40 text-xs text-amber-200">
            <strong>Data Safety Guarantee:</strong> Deleting this investigation case deletes associated evidence milestones and case notes. Raw source surveillance videos and AI object detections remain preserved in your archive.
          </div>
          <div className="flex items-center justify-end gap-2 pt-2">
            <Button variant="ghost" size="sm" onClick={() => setIsDeleteModalOpen(false)}>
              Cancel
            </Button>
            <Button
              variant="primary"
              size="sm"
              onClick={() => deleteCaseMutation.mutate()}
              disabled={deleteCaseMutation.isPending}
              className="bg-red-500 hover:bg-red-600 text-white font-semibold"
            >
              {deleteCaseMutation.isPending ? 'Deleting...' : 'Delete Case Permanently'}
            </Button>
          </div>
        </div>
      </Modal>

      {/* ── Video Player Modal Seeked to Evidence Timestamp ── */}
      {playerVideo && (
        <VideoPlayerModal
          video={playerVideo}
          isOpen={isPlayerOpen}
          initialTimestamp={playerTimestamp}
          onClose={() => {
            setIsPlayerOpen(false)
            setPlayerVideo(null)
            setPlayerTimestamp(null)
          }}
        />
      )}
    </div>
  )
}
export default CaseWorkspacePage
