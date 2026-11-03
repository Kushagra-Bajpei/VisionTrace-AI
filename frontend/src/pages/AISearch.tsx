/**
 * AISearchPage – Natural Language & Visual Similarity CCTV Investigation Search.
 * Translates conversational queries & visual descriptions into verified evidence records.
 * Integrates directly with VideoPlayerModal for seamless one-click evidence playback.
 */
import { useEffect, useState } from 'react'
import { useSearchParams, Link } from 'react-router-dom'
import {
  Search,
  Sparkles,
  Target,
  Crosshair,
  Film,
  Play,
  RotateCw,
  X,
  Eye,
  FolderPlus,
  Check,
  ExternalLink,
  User,
  Car,
  Compass,
  SlidersHorizontal,
  ChevronRight,
} from 'lucide-react'
import { Card, CardContent } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Modal } from '@/components/ui/Modal'
import { Spinner } from '@/components/ui/Loading'
import { VideoPlayerModal } from '@/components/video/VideoPlayerModal'
import { searchService } from '@/services/search'
import { videoService } from '@/services/video'
import { investigationService } from '@/services/investigation'
import { formatDuration, getResolutionLabel } from '@/lib/utils'
import type {
  InvestigationCase,
  SearchQueryResponse,
  SearchSuggestion,
  Video,
} from '@/types'

export function AISearchPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const initialQuery = searchParams.get('q') || ''

  const [query, setQuery] = useState(initialQuery)
  const [selectedVideoId, setSelectedVideoId] = useState<string>(searchParams.get('video_id') || '')
  const [selectedClass] = useState<string>('')
  const [minConfidence] = useState<number | undefined>(undefined)
  const [visualSearchEnabled, setVisualSearchEnabled] = useState<boolean>(true)

  const [availableVideos, setAvailableVideos] = useState<Video[]>([])
  const [suggestions, setSuggestions] = useState<SearchSuggestion[]>([])
  const [results, setResults] = useState<SearchQueryResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [viewMode, setViewMode] = useState<'tracks' | 'detections' | 'visual'>('tracks')

  // Selected video for Player Modal
  const [modalVideo, setModalVideo] = useState<Video | null>(null)
  const [modalOpen, setModalOpen] = useState(false)
  const [seekTarget, setSeekTarget] = useState<number | null>(null)

  // Add to Case Modal State (Phase 7)
  const [caseModalOpen, setCaseModalOpen] = useState(false)
  const [evidenceTarget, setEvidenceTarget] = useState<{
    video_id: string
    timestamp: number
    event_id?: string | null
    track_id?: string | null
    object_class: string
    confidence?: number
    visual_similarity_score?: number | null
    frame_path?: string | null
    crop_path?: string | null
    evidence_type: 'detection' | 'tracked_object'
    video_name: string
  } | null>(null)
  const [availableCases, setAvailableCases] = useState<InvestigationCase[]>([])
  const [selectedCaseId, setSelectedCaseId] = useState<string>('')
  const [newCaseTitle, setNewCaseTitle] = useState<string>('')
  const [evidenceNotes, setEvidenceNotes] = useState<string>('')
  const [isSubmittingEvidence, setIsSubmittingEvidence] = useState(false)
  const [caseSuccessId, setCaseSuccessId] = useState<string | null>(null)

  // Load available videos and query suggestions on mount
  useEffect(() => {
    videoService.listVideos().then((vids) => setAvailableVideos(vids)).catch(() => {})
    searchService.getSuggestions().then((s) => setSuggestions(s)).catch(() => {})
  }, [])

  // Execute search when query or video filter changes from URL
  useEffect(() => {
    if (initialQuery.trim()) {
      executeSearch(initialQuery)
    }
  }, [initialQuery])

  const executeSearch = async (queryText: string) => {
    const q = queryText.trim()
    if (!q) return

    setLoading(true)
    setError(null)
    setSearchParams({ q, ...(selectedVideoId ? { video_id: selectedVideoId } : {}) })

    try {
      const data = await searchService.searchQuery({
        query: q,
        video_id: selectedVideoId || undefined,
        object_class: selectedClass || undefined,
        min_confidence: minConfidence,
        visual_search: visualSearchEnabled,
        limit: 100,
      })
      setResults(data)

      const hasVisualMatches = data.detections.some((d) => d.visual_similarity_score !== undefined && d.visual_similarity_score !== null)
      if (hasVisualMatches) {
        setViewMode('visual')
      } else if (data.tracks.length === 0 && data.detections.length > 0) {
        setViewMode('detections')
      } else {
        setViewMode('tracks')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Search query execution failed')
      setResults(null)
    } finally {
      setLoading(false)
    }
  }

  const handleSuggestionClick = (templateQuery: string) => {
    setQuery(templateQuery)
    executeSearch(templateQuery)
  }

  const handleOpenEvidence = async (videoId: string, timestampSeconds: number) => {
    try {
      const v = await videoService.getVideo(videoId)
      setModalVideo(v)
      setSeekTarget(timestampSeconds)
      setModalOpen(true)
    } catch {
      alert('Could not open video asset for evidence playback')
    }
  }

  const handleOpenAddToCase = async (item: {
    video_id: string
    timestamp: number
    event_id?: string | null
    track_id?: string | null
    object_class: string
    confidence?: number
    visual_similarity_score?: number | null
    frame_path?: string | null
    crop_path?: string | null
    evidence_type: 'detection' | 'tracked_object'
    video_name: string
  }) => {
    setEvidenceTarget(item)
    setCaseSuccessId(null)
    setEvidenceNotes('')
    setNewCaseTitle('')
    setCaseModalOpen(true)
    try {
      const cases = await investigationService.listCases({ status: 'open' })
      setAvailableCases(cases)
      if (cases.length > 0) {
        setSelectedCaseId(cases[0].id)
      } else {
        setSelectedCaseId('new')
      }
    } catch {
      setSelectedCaseId('new')
    }
  }

  const handleConfirmAddToCase = async () => {
    if (!evidenceTarget) return
    setIsSubmittingEvidence(true)
    try {
      let targetId = selectedCaseId
      if (targetId === 'new' || !targetId) {
        if (!newCaseTitle.trim()) {
          setIsSubmittingEvidence(false)
          return
        }
        const created = await investigationService.createCase({
          title: newCaseTitle.trim(),
          priority: 'medium',
          status: 'open',
          tags: [evidenceTarget.object_class.toLowerCase()],
        })
        targetId = created.id
      }

      await investigationService.addEvidence(targetId, {
        video_id: evidenceTarget.video_id,
        timestamp: evidenceTarget.timestamp,
        event_id: evidenceTarget.event_id,
        track_id: evidenceTarget.track_id,
        evidence_type: evidenceTarget.evidence_type,
        object_class: evidenceTarget.object_class,
        confidence: evidenceTarget.confidence,
        visual_similarity_score: evidenceTarget.visual_similarity_score,
        frame_path: evidenceTarget.frame_path,
        crop_path: evidenceTarget.crop_path,
        notes: evidenceNotes.trim() || undefined,
      })

      setCaseSuccessId(targetId)
    } catch (err) {
      console.error('Failed to link evidence to case:', err)
    } finally {
      setIsSubmittingEvidence(false)
    }
  }

  const visualMatches = results?.detections.filter((d) => d.visual_similarity_score !== undefined && d.visual_similarity_score !== null) || []

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12">
      {/* Search Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-[var(--color-text-primary)]">
              AI Video Search
            </h1>
            <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-cyan-950/80 text-[var(--color-accent)] border border-cyan-800/40 uppercase">
              Phase 6: Visual Similarity
            </span>
          </div>
          <p className="text-xs sm:text-sm text-[var(--color-text-muted)] mt-1 font-mono">
            Query surveillance footage using natural language and visual appearance descriptions (CLIP ViT-B-32 multimodal ranking).
          </p>
        </div>

        {/* View Mode Toggle when results exist */}
        {results && results.total_matches > 0 && (
          <div className="flex items-center gap-1.5 p-1 rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)] text-xs font-mono">
            {visualMatches.length > 0 && (
              <button
                onClick={() => setViewMode('visual')}
                className={`px-3 py-1 rounded transition-all cursor-pointer flex items-center gap-1.5 ${
                  viewMode === 'visual'
                    ? 'bg-[var(--color-accent)] text-[#05080c] font-black'
                    : 'text-[var(--color-text-secondary)] hover:text-white'
                }`}
              >
                <Eye className="w-3.5 h-3.5" />
                <span>Visual Ranking ({visualMatches.length})</span>
              </button>
            )}
            <button
              onClick={() => setViewMode('tracks')}
              className={`px-3 py-1 rounded transition-all cursor-pointer ${
                viewMode === 'tracks'
                  ? 'bg-[var(--color-accent)] text-[#05080c] font-black'
                  : 'text-[var(--color-text-secondary)] hover:text-white'
              }`}
            >
              Tracks ({results.total_tracks})
            </button>
            <button
              onClick={() => setViewMode('detections')}
              className={`px-3 py-1 rounded transition-all cursor-pointer ${
                viewMode === 'detections'
                  ? 'bg-[var(--color-accent)] text-[#05080c] font-black'
                  : 'text-[var(--color-text-secondary)] hover:text-white'
              }`}
            >
              Keyframes ({results.total_matches})
            </button>
            <button
              onClick={() => {
                setResults(null)
                setQuery('')
                setSearchParams({})
              }}
              className="px-2.5 py-1 rounded text-[11px] text-[var(--color-text-muted)] hover:text-white border-l border-[var(--color-border)] ml-1 cursor-pointer transition-colors"
              title="Reset search and return to discovery canvas"
            >
              Reset
            </button>
          </div>
        )}
      </div>

      {/* Main Search Bar & Filter Strip */}
      <Card className="border-[var(--color-border-2)] bg-[var(--color-surface)]/80 shadow-2xl backdrop-blur-sm">
        <CardContent className="p-4 sm:p-5 space-y-3">
          <form
            onSubmit={(e) => {
              e.preventDefault()
              executeSearch(query)
            }}
            className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2.5"
          >
            <div className="relative flex-1">
              <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--color-accent)] pointer-events-none" />
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search footage with natural language or visual appearance descriptions..."
                className="w-full pl-10 pr-10 py-2.5 rounded-lg bg-[var(--color-surface-2)] border border-[var(--color-border)] text-sm font-mono text-white placeholder:text-[var(--color-text-muted)] focus:outline-none focus:border-[var(--color-accent)] focus:ring-1 focus:ring-[var(--color-accent)] transition-all"
              />
              {query && (
                <button
                  type="button"
                  onClick={() => setQuery('')}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--color-text-muted)] hover:text-white p-1 cursor-pointer"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              )}
            </div>

            {/* Video Asset Dropdown */}
            <select
              value={selectedVideoId}
              onChange={(e) => setSelectedVideoId(e.target.value)}
              className="px-3 py-2.5 rounded-lg bg-[var(--color-surface-2)] border border-[var(--color-border)] text-xs font-mono text-[var(--color-text-secondary)] focus:outline-none focus:border-[var(--color-accent)] cursor-pointer"
            >
              <option value="">All Video Feeds</option>
              {availableVideos.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.original_filename}
                </option>
              ))}
            </select>

            {/* Visual Similarity Mode Toggle */}
            <button
              type="button"
              onClick={() => setVisualSearchEnabled(!visualSearchEnabled)}
              className={`px-3 py-2.5 rounded-lg border text-xs font-mono flex items-center gap-1.5 transition-all cursor-pointer shrink-0 ${
                visualSearchEnabled
                  ? 'bg-cyan-950/80 border-cyan-700/60 text-[var(--color-accent)]'
                  : 'bg-[var(--color-surface-2)] border-[var(--color-border)] text-[var(--color-text-muted)]'
              }`}
              title="Toggle CLIP Visual Similarity Ranking"
            >
              <Sparkles className="w-3.5 h-3.5" />
              <span>Visual CLIP</span>
            </button>

            <Button
              type="submit"
              variant="primary"
              disabled={loading || !query.trim()}
              className="gap-2 shrink-0 py-2.5"
            >
              <Sparkles className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
              <span>{loading ? 'Ranking Evidence…' : 'Search Footage'}</span>
            </Button>
          </form>

          {/* Suggested Queries Pill Strip without raw scrollbar */}
          {suggestions.length > 0 && (
            <div className="pt-2 border-t border-[var(--color-border)]/60 flex items-center gap-2 overflow-x-auto no-scrollbar pb-1">
              <span className="text-[10px] font-mono uppercase text-[var(--color-text-muted)] shrink-0 flex items-center gap-1">
                <Target className="w-3 h-3 text-[var(--color-accent)]" />
                Quick Presets:
              </span>
              {suggestions.map((s) => (
                <button
                  key={s.query}
                  type="button"
                  onClick={() => handleSuggestionClick(s.query)}
                  className="shrink-0 px-2.5 py-1 rounded text-[11px] font-mono bg-[var(--color-surface-2)] border border-[var(--color-border)] hover:border-[var(--color-accent)] text-[var(--color-text-secondary)] hover:text-white transition-all cursor-pointer"
                  title={s.description}
                >
                  {s.query}
                </button>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Loading Skeleton State */}
      {loading && (
        <div className="p-8 rounded-xl bg-[var(--color-surface)] border border-[var(--color-border)] text-center space-y-3">
          <RotateCw className="w-6 h-6 animate-spin text-[var(--color-accent)] mx-auto" />
          <p className="text-xs font-mono text-[var(--color-text-muted)]">
            Comparing query embedding with CCTV keyframes and object crops via CLIP ViT-B-32...
          </p>
        </div>
      )}

      {/* Error State */}
      {error && !loading && (
        <div className="p-4 rounded-xl bg-rose-950/20 border border-rose-500/30 text-rose-300 text-xs font-mono flex items-center justify-between">
          <span>{error}</span>
          <Button variant="outline" size="xs" onClick={() => executeSearch(query)}>
            Retry
          </Button>
        </div>
      )}

      {/* Search Results Display */}
      {results && !loading && (
        <div className="space-y-6">
          {/* Grounded AI Briefing Card */}
          <div className="p-4 sm:p-5 rounded-xl bg-gradient-to-r from-[#070b12] to-[#0c1322] border border-cyan-800/40 shadow-xl space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-[var(--color-accent)]" />
                <span className="text-xs font-mono uppercase font-bold text-[var(--color-accent)]">
                  Forensic Intelligence Briefing
                </span>
                {results.parsed_facets.is_visual_search && (
                  <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-cyan-950/90 text-cyan-300 border border-cyan-700/60 uppercase">
                    CLIP Visual Similarity Ranking Active
                  </span>
                )}
              </div>
              <span className="text-[10px] font-mono text-[var(--color-text-muted)]">
                {results.total_matches} Verified Detection(s) • {results.total_tracks} Track(s)
              </span>
            </div>

            {/* Factual Evidence Narrative */}
            <p className="text-xs sm:text-sm font-mono text-slate-200 leading-relaxed">
              {results.evidence_summary}
            </p>

            {/* Parsed Search Facet Badges */}
            <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-white/5 text-[10px] font-mono">
              <span className="text-[var(--color-text-muted)] uppercase">Parsed Facets:</span>

              {results.parsed_facets.target_classes.length > 0 && (
                <span className="px-2 py-0.5 rounded bg-cyan-950 text-[var(--color-accent)] border border-cyan-800/40 capitalize">
                  Class: {results.parsed_facets.target_classes.join(', ')}
                </span>
              )}

              {results.parsed_facets.visual_descriptors && results.parsed_facets.visual_descriptors.length > 0 && (
                <span className="px-2 py-0.5 rounded bg-cyan-900/40 text-cyan-200 border border-cyan-700/50">
                  Visual Cues: {results.parsed_facets.visual_descriptors.join(', ')}
                </span>
              )}

              {results.parsed_facets.time_min !== null && results.parsed_facets.time_min !== undefined && (
                <span className="px-2 py-0.5 rounded bg-[var(--color-surface-2)] text-[var(--color-text-secondary)] border border-[var(--color-border)]">
                  Window: {formatDuration(results.parsed_facets.time_min)} → {results.parsed_facets.time_max ? formatDuration(results.parsed_facets.time_max) : 'End'}
                </span>
              )}

              {results.parsed_facets.min_confidence && (
                <span className="px-2 py-0.5 rounded bg-[var(--color-surface-2)] text-[var(--color-text-secondary)] border border-[var(--color-border)]">
                  Min Conf: {Math.round(results.parsed_facets.min_confidence * 100)}%
                </span>
              )}

              {results.parsed_facets.track_number && (
                <span className="px-2 py-0.5 rounded bg-[var(--color-surface-2)] text-[var(--color-text-secondary)] border border-[var(--color-border)]">
                  Target ID: #{results.parsed_facets.track_number}
                </span>
              )}

              {/* Unsupported Facets Warnings */}
              {results.parsed_facets.unsupported_facets.length > 0 && (
                <span className="px-2 py-0.5 rounded bg-amber-950/60 text-amber-300 border border-amber-800/40">
                  Ignored: {results.parsed_facets.unsupported_facets.join(', ')}
                </span>
              )}
            </div>
          </div>

          {/* Empty State */}
          {results.total_matches === 0 && (
            <div className="p-12 rounded-xl bg-[var(--color-surface)] border border-[var(--color-border)] text-center space-y-3">
              <Crosshair className="w-10 h-10 text-[var(--color-text-muted)] mx-auto opacity-50" />
              <h3 className="text-sm font-mono font-bold text-white">No Target Evidence Located</h3>
              <p className="text-xs font-mono text-[var(--color-text-muted)] max-w-md mx-auto">
                No surveillance footage matched your query parameters. Try widening the confidence threshold, expanding the time window, or testing another visual description.
              </p>
            </div>
          )}

          {/* VIEW 0: VISUAL SIMILARITY EVIDENCE CARDS */}
          {viewMode === 'visual' && visualMatches.length > 0 && (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
              {visualMatches.map((det) => (
                <div
                  key={det.id}
                  className="rounded-xl overflow-hidden bg-[var(--color-surface)] border border-cyan-800/40 hover:border-[var(--color-accent)] transition-all flex flex-col justify-between group shadow-xl"
                >
                  <div className="relative aspect-video bg-black overflow-hidden flex items-center justify-center">
                    {det.annotated_frame_url ? (
                      <img
                        src={det.annotated_frame_url}
                        alt={`${det.object_class} detection`}
                        className="w-full h-full object-cover group-hover:scale-105 transition-transform"
                        loading="lazy"
                      />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center text-[var(--color-text-muted)]">
                        <Film className="w-8 h-8 opacity-40" />
                      </div>
                    )}

                    {/* High-Resolution Detection Crop Inset */}
                    {det.crop_image_url && (
                      <div className="absolute bottom-2 left-2 w-16 h-16 sm:w-20 sm:h-20 rounded-lg overflow-hidden border-2 border-[var(--color-accent)] bg-black/90 shadow-2xl z-10 group/crop">
                        <img
                          src={det.crop_image_url}
                          alt="Cropped target"
                          className="w-full h-full object-cover group-hover/crop:scale-110 transition-transform"
                          loading="lazy"
                        />
                        <span className="absolute bottom-0 inset-x-0 bg-black/80 text-[8px] font-mono text-center text-cyan-300 font-bold uppercase">
                          Target Crop
                        </span>
                      </div>
                    )}

                    {/* Telemetry Overlays */}
                    <div className="absolute top-2 left-2 flex items-center gap-1.5 z-10">
                      <span className="px-2 py-0.5 rounded bg-black/80 backdrop-blur-md text-white text-[10px] font-mono font-bold capitalize">
                        {det.object_class}
                      </span>
                      {det.track_number && (
                        <span className="px-2 py-0.5 rounded bg-cyan-950/80 text-[var(--color-accent)] border border-cyan-800/40 text-[10px] font-mono font-bold">
                          Track #{det.track_number}
                        </span>
                      )}
                    </div>

                    <div className="absolute top-2 right-2 px-2 py-0.5 rounded bg-cyan-950/90 text-[var(--color-accent)] border border-cyan-700/60 font-mono text-[11px] font-bold z-10 shadow-lg">
                      Visual Similarity: {Math.round((det.visual_similarity_score || 0) * 100)}%
                    </div>

                    <div className="absolute bottom-2 right-2 px-2 py-0.5 rounded bg-black/80 text-white font-mono text-[10px] font-bold z-10">
                      {formatDuration(det.timestamp)}
                    </div>
                  </div>

                  <div className="p-3.5 space-y-3">
                    <div className="flex items-center justify-between text-xs font-mono">
                      <span className="text-[var(--color-text-muted)] truncate max-w-[180px]">
                        {det.video_name}
                      </span>
                      <span className="text-emerald-400 font-bold" title="YOLO Object Detector Confidence">
                        Detector Conf: {Math.round(det.confidence * 100)}%
                      </span>
                    </div>

                    <div className="p-2 rounded bg-[var(--color-surface-2)] border border-[var(--color-border)] text-[10px] font-mono text-[var(--color-text-secondary)]">
                      <span className="text-[var(--color-accent)] font-bold">Visual Ranking: </span>
                      Match score based on CLIP vision-language alignment against query "{query}".
                    </div>

                    <Button
                      variant="outline"
                      size="xs"
                      onClick={() => handleOpenEvidence(det.video_id, det.timestamp)}
                      className="w-full gap-1.5 justify-center font-mono text-xs text-[var(--color-accent)] border-cyan-800/50 hover:bg-cyan-950/40 cursor-pointer"
                    >
                      <Play className="w-3.5 h-3.5 fill-current" />
                      <span>View Evidence (Seek {formatDuration(det.timestamp)})</span>
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* VIEW 1: TARGET TRACKS */}
          {viewMode === 'tracks' && results.tracks.length > 0 && (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {results.tracks.map((trk) => (
                <div
                  key={trk.id}
                  className="p-4 rounded-xl bg-[var(--color-surface)] border border-[var(--color-border)] hover:border-[var(--color-border-accent)] hover:shadow-lg transition-all space-y-3 flex flex-col justify-between group"
                >
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="w-7 h-7 rounded bg-black/60 text-[var(--color-accent)] border border-cyan-800/40 font-bold flex items-center justify-center text-xs font-mono">
                          #{trk.track_id}
                        </span>
                        <div>
                          <span className="font-bold text-white capitalize text-sm font-mono">
                            {trk.object_class}
                          </span>
                          <span className="text-[10px] font-mono text-[var(--color-text-muted)] block">
                            {trk.video_name}
                          </span>
                        </div>
                      </div>

                      <span className="px-2 py-0.5 rounded bg-emerald-950/60 text-emerald-400 border border-emerald-800/40 text-xs font-mono font-bold" title="Average Detector Confidence">
                        {Math.round(trk.confidence_avg * 100)}%
                      </span>
                    </div>

                    <div className="p-2.5 rounded-lg bg-[var(--color-surface-2)] border border-[var(--color-border)]/60 text-[11px] font-mono space-y-1.5">
                      <div className="flex items-center justify-between text-[var(--color-text-secondary)]">
                        <span>Observed Interval:</span>
                        <span className="font-bold text-white">
                          {formatDuration(trk.start_time)} → {formatDuration(trk.end_time)}
                        </span>
                      </div>
                      <div className="flex items-center justify-between text-[var(--color-text-secondary)]">
                        <span>Frames Span:</span>
                        <span>
                          #{trk.start_frame} → #{trk.end_frame} ({trk.detection_count} hits)
                        </span>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    <Button
                      variant="outline"
                      size="xs"
                      onClick={() => handleOpenEvidence(trk.video_id, trk.start_time)}
                      className="flex-1 gap-1.5 justify-center font-mono text-xs text-[var(--color-accent)] border-cyan-800/50 hover:bg-cyan-950/40 cursor-pointer"
                    >
                      <Play className="w-3.5 h-3.5 fill-current" />
                      <span>Seek {formatDuration(trk.start_time)}</span>
                    </Button>
                    <Button
                      variant="ghost"
                      size="xs"
                      onClick={() =>
                        handleOpenAddToCase({
                          video_id: trk.video_id,
                          timestamp: trk.start_time,
                          track_id: trk.id,
                          object_class: trk.object_class,
                          confidence: trk.confidence_avg,
                          evidence_type: 'tracked_object',
                          video_name: trk.video_name,
                        })
                      }
                      className="text-xs border border-[var(--color-border)] hover:border-[var(--color-accent)] text-[var(--color-text-secondary)] hover:text-[var(--color-accent)] px-2.5"
                      title="Attach Track to Investigation Case"
                    >
                      <FolderPlus className="w-3.5 h-3.5 mr-1" />
                      Case
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* VIEW 2: KEYFRAME DETECTIONS */}
          {viewMode === 'detections' && results.detections.length > 0 && (
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
              {results.detections.map((det) => (
                <div
                  key={det.id}
                  className="rounded-xl overflow-hidden bg-[var(--color-surface)] border border-[var(--color-border)] hover:border-[var(--color-border-accent)] transition-all flex flex-col justify-between group"
                >
                  <div className="relative aspect-video bg-black overflow-hidden">
                    {det.annotated_frame_url ? (
                      <img
                        src={det.annotated_frame_url}
                        alt={`${det.object_class} detection`}
                        className="w-full h-full object-cover group-hover:scale-105 transition-transform"
                        loading="lazy"
                      />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center text-[var(--color-text-muted)]">
                        <Film className="w-8 h-8 opacity-40" />
                      </div>
                    )}
                    <div className="absolute top-2 left-2 flex items-center gap-1.5">
                      <span className="px-1.5 py-0.5 rounded bg-black/80 backdrop-blur-md text-white text-[10px] font-mono font-bold capitalize">
                        {det.object_class}
                      </span>
                      {det.track_number && (
                        <span className="px-1.5 py-0.5 rounded bg-cyan-950/80 text-[var(--color-accent)] border border-cyan-800/40 text-[10px] font-mono font-bold">
                          #{det.track_number}
                        </span>
                      )}
                    </div>
                    {det.visual_similarity_score !== undefined && det.visual_similarity_score !== null && (
                      <div className="absolute top-2 right-2 px-1.5 py-0.5 rounded bg-cyan-950/90 text-[var(--color-accent)] border border-cyan-700/60 font-mono text-[10px] font-bold">
                        Sim: {Math.round(det.visual_similarity_score * 100)}%
                      </div>
                    )}
                    <div className="absolute bottom-2 right-2 px-1.5 py-0.5 rounded bg-black/80 text-white font-mono text-[10px] font-bold">
                      {formatDuration(det.timestamp)}
                    </div>
                  </div>

                  <div className="p-3 space-y-2">
                    <div className="flex items-center justify-between text-xs font-mono">
                      <span className="text-[var(--color-text-muted)] truncate max-w-[140px]">
                        {det.video_name}
                      </span>
                      <span className="text-emerald-400 font-bold" title="Detector Confidence">
                        {Math.round(det.confidence * 100)}%
                      </span>
                    </div>

                    <div className="flex items-center gap-1.5">
                      <Button
                        variant="outline"
                        size="xs"
                        onClick={() => handleOpenEvidence(det.video_id, det.timestamp)}
                        className="flex-1 gap-1 justify-center font-mono text-[11px] text-[var(--color-accent)] border-cyan-800/50 hover:bg-cyan-950/40 cursor-pointer"
                      >
                        <Play className="w-3 h-3 fill-current" />
                        <span>Seek {formatDuration(det.timestamp)}</span>
                      </Button>
                      <Button
                        variant="ghost"
                        size="xs"
                        onClick={() =>
                          handleOpenAddToCase({
                            video_id: det.video_id,
                            timestamp: det.timestamp,
                            event_id: det.id,
                            track_id: det.track_id,
                            object_class: det.object_class,
                            confidence: det.confidence,
                            visual_similarity_score: det.visual_similarity_score,
                            frame_path: det.frame_path,
                            evidence_type: 'detection',
                            video_name: det.video_name,
                          })
                        }
                        className="text-xs border border-[var(--color-border)] hover:border-[var(--color-accent)] text-[var(--color-text-secondary)] hover:text-[var(--color-accent)] px-2"
                        title="Add to Investigation Case"
                      >
                        <FolderPlus className="w-3.5 h-3.5" />
                      </Button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* INITIAL EMPTY STATE: TACTICAL DISCOVERY CANVAS */}
      {!results && !loading && (
        <div className="space-y-8 animate-in fade-in duration-300">
          {/* Quick-Start Investigation Presets */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Target className="w-4 h-4 text-[var(--color-accent)]" />
                <h3 className="text-xs font-mono font-bold uppercase tracking-wider text-[var(--color-text-primary)]">
                  Tactical Surveillance Query Presets
                </h3>
              </div>
              <span className="text-[10px] font-mono text-[var(--color-text-muted)]">
                Click any preset to execute live multimodal investigation
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {/* Category 1: Persons of Interest */}
              <div className="p-4 rounded-xl bg-[var(--color-surface)] border border-[var(--color-border)] hover:border-cyan-800/60 transition-all space-y-3 flex flex-col justify-between shadow-sm">
                <div className="space-y-2">
                  <div className="flex items-center gap-2 text-xs font-mono font-bold text-cyan-300">
                    <span className="p-1 rounded bg-cyan-950/80 border border-cyan-800/40">
                      <User className="w-3.5 h-3.5 text-[var(--color-accent)]" />
                    </span>
                    <span>Person of Interest & Apparel</span>
                  </div>
                  <p className="text-[11px] font-mono text-[var(--color-text-muted)] leading-relaxed">
                    Filter by pedestrian detections, visual clothing colors, and carried objects using CLIP embeddings.
                  </p>
                </div>

                <div className="space-y-1.5 pt-2 border-t border-[var(--color-border)]">
                  {[
                    { q: 'Find all people detected in this video', label: 'All Pedestrian Detections' },
                    { q: 'Person wearing a dark jacket', label: 'Dark Jacket / Outerwear' },
                    { q: 'Someone carrying a backpack or bag', label: 'Carried Bag / Accessory' },
                  ].map((item) => (
                    <button
                      key={item.q}
                      type="button"
                      onClick={() => handleSuggestionClick(item.q)}
                      className="w-full text-left px-2.5 py-1.5 rounded-lg bg-[var(--color-surface-2)] hover:bg-cyan-950/40 border border-transparent hover:border-cyan-800/40 text-xs font-mono text-slate-300 hover:text-cyan-300 transition-all flex items-center justify-between group/btn cursor-pointer"
                    >
                      <span className="truncate">{item.label}</span>
                      <ChevronRight className="w-3 h-3 text-[var(--color-text-muted)] group-hover/btn:text-[var(--color-accent)] group-hover/btn:translate-x-0.5 transition-all shrink-0" />
                    </button>
                  ))}
                </div>
              </div>

              {/* Category 2: Vehicles & Ingress */}
              <div className="p-4 rounded-xl bg-[var(--color-surface)] border border-[var(--color-border)] hover:border-cyan-800/60 transition-all space-y-3 flex flex-col justify-between shadow-sm">
                <div className="space-y-2">
                  <div className="flex items-center gap-2 text-xs font-mono font-bold text-cyan-300">
                    <span className="p-1 rounded bg-cyan-950/80 border border-cyan-800/40">
                      <Car className="w-3.5 h-3.5 text-[var(--color-accent)]" />
                    </span>
                    <span>Vehicle & Perimeter Tracking</span>
                  </div>
                  <p className="text-[11px] font-mono text-[var(--color-text-muted)] leading-relaxed">
                    Target vehicle classes, colors, and chronological arrival windows across surveillance feeds.
                  </p>
                </div>

                <div className="space-y-1.5 pt-2 border-t border-[var(--color-border)]">
                  {[
                    { q: 'Show me cars visible between 00:00 and 00:05', label: 'Cars Visible 00:00 – 00:05' },
                    { q: 'White car or truck near entrance', label: 'White Vehicle at Entrance' },
                    { q: 'Find all vehicles with confidence above 80%', label: 'High Confidence Vehicles (>80%)' },
                  ].map((item) => (
                    <button
                      key={item.q}
                      type="button"
                      onClick={() => handleSuggestionClick(item.q)}
                      className="w-full text-left px-2.5 py-1.5 rounded-lg bg-[var(--color-surface-2)] hover:bg-cyan-950/40 border border-transparent hover:border-cyan-800/40 text-xs font-mono text-slate-300 hover:text-cyan-300 transition-all flex items-center justify-between group/btn cursor-pointer"
                    >
                      <span className="truncate">{item.label}</span>
                      <ChevronRight className="w-3 h-3 text-[var(--color-text-muted)] group-hover/btn:text-[var(--color-accent)] group-hover/btn:translate-x-0.5 transition-all shrink-0" />
                    </button>
                  ))}
                </div>
              </div>

              {/* Category 3: Spatiotemporal & Tracks */}
              <div className="p-4 rounded-xl bg-[var(--color-surface)] border border-[var(--color-border)] hover:border-cyan-800/60 transition-all space-y-3 flex flex-col justify-between shadow-sm">
                <div className="space-y-2">
                  <div className="flex items-center gap-2 text-xs font-mono font-bold text-cyan-300">
                    <span className="p-1 rounded bg-cyan-950/80 border border-cyan-800/40">
                      <Compass className="w-3.5 h-3.5 text-[var(--color-accent)]" />
                    </span>
                    <span>ByteTrack & Temporal Facets</span>
                  </div>
                  <p className="text-[11px] font-mono text-[var(--color-text-muted)] leading-relaxed">
                    Retrieve persistent trajectories by track identifier, confidence threshold, or last sighting time.
                  </p>
                </div>

                <div className="space-y-1.5 pt-2 border-t border-[var(--color-border)]">
                  {[
                    { q: 'Find all objects for Track #1', label: 'Track #1 Trajectory History' },
                    { q: 'When was a person last seen?', label: 'Latest Temporal Sighting' },
                    { q: 'Show tracks with confidence above 80%', label: 'Verified Tracks (>80% Avg Conf)' },
                  ].map((item) => (
                    <button
                      key={item.q}
                      type="button"
                      onClick={() => handleSuggestionClick(item.q)}
                      className="w-full text-left px-2.5 py-1.5 rounded-lg bg-[var(--color-surface-2)] hover:bg-cyan-950/40 border border-transparent hover:border-cyan-800/40 text-xs font-mono text-slate-300 hover:text-cyan-300 transition-all flex items-center justify-between group/btn cursor-pointer"
                    >
                      <span className="truncate">{item.label}</span>
                      <ChevronRight className="w-3 h-3 text-[var(--color-text-muted)] group-hover/btn:text-[var(--color-accent)] group-hover/btn:translate-x-0.5 transition-all shrink-0" />
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* Available Surveillance Feeds (Target Selector Grid) */}
          {availableVideos.length > 0 && (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Film className="w-4 h-4 text-[var(--color-accent)]" />
                  <h3 className="text-xs font-mono font-bold uppercase tracking-wider text-[var(--color-text-primary)]">
                    Active Surveillance Feeds ({availableVideos.length})
                  </h3>
                </div>
                <span className="text-[10px] font-mono text-[var(--color-text-muted)]">
                  Target a specific video or search across all assets
                </span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {availableVideos.map((v) => {
                  const isSelected = selectedVideoId === v.id
                  const thumbUrl = v.thumbnail_path ? videoService.getThumbnailUrl(v.id) : null

                  return (
                    <div
                      key={v.id}
                      className={`p-3.5 rounded-xl border transition-all flex flex-col justify-between gap-3 group/feed bg-[var(--color-surface)] ${
                        isSelected
                          ? 'border-[var(--color-accent)] ring-1 ring-[var(--color-accent)]/40 shadow-[0_0_15px_rgba(0,229,255,0.15)]'
                          : 'border-[var(--color-border)] hover:border-cyan-800/50'
                      }`}
                    >
                      <div className="flex items-start gap-3">
                        <div
                          onClick={() => handleOpenEvidence(v.id, 0)}
                          className="relative w-24 aspect-video rounded-lg overflow-hidden bg-black shrink-0 border border-white/10 cursor-pointer group/thumb"
                        >
                          {thumbUrl ? (
                            <img
                              src={thumbUrl}
                              alt={v.original_filename}
                              className="w-full h-full object-cover group-hover/thumb:scale-105 transition-transform"
                            />
                          ) : (
                            <div className="w-full h-full flex items-center justify-center text-[var(--color-text-muted)]">
                              <Film className="w-5 h-5 opacity-40" />
                            </div>
                          )}
                          <div className="absolute inset-0 bg-black/40 flex items-center justify-center opacity-0 group-hover/thumb:opacity-100 transition-opacity">
                            <Play className="w-4 h-4 text-[var(--color-accent)] fill-current" />
                          </div>
                          <div className="absolute bottom-1 right-1 px-1 rounded bg-black/80 text-[8px] font-mono font-bold text-white">
                            {formatDuration(v.duration)}
                          </div>
                        </div>

                        <div className="space-y-1 min-w-0 flex-1">
                          <p className="text-xs font-mono font-bold text-white truncate" title={v.original_filename}>
                            {v.original_filename}
                          </p>
                          <div className="flex flex-wrap items-center gap-1.5">
                            <Badge variant="telemetry">{getResolutionLabel(v.width, v.height)}</Badge>
                            {v.fps && <Badge variant="telemetry">{v.fps} FPS</Badge>}
                            {v.video_metadata?.tracks_count !== undefined && v.video_metadata.tracks_count > 0 && (
                              <span className="px-1.5 py-0.5 rounded bg-cyan-950 text-[var(--color-accent)] border border-cyan-800/40 text-[9px] font-mono font-bold">
                                {v.video_metadata.tracks_count} TRACKS
                              </span>
                            )}
                          </div>
                        </div>
                      </div>

                      <div className="flex items-center justify-between pt-2 border-t border-[var(--color-border)] text-xs font-mono">
                        <button
                          type="button"
                          onClick={() => {
                            if (isSelected) {
                              setSelectedVideoId('')
                            } else {
                              setSelectedVideoId(v.id)
                            }
                          }}
                          className={`px-2.5 py-1 rounded text-[11px] font-mono transition-all cursor-pointer flex items-center gap-1 ${
                            isSelected
                              ? 'bg-[var(--color-accent)] text-[#05080c] font-black'
                              : 'bg-[var(--color-surface-2)] text-[var(--color-text-secondary)] hover:text-white border border-[var(--color-border)] hover:border-cyan-800/40'
                          }`}
                        >
                          <Crosshair className="w-3 h-3" />
                          <span>{isSelected ? 'Targeted Active' : 'Target This Feed'}</span>
                        </button>

                        <button
                          type="button"
                          onClick={() => handleOpenEvidence(v.id, 0)}
                          className="text-[11px] text-[var(--color-text-muted)] hover:text-cyan-300 transition-colors flex items-center gap-1 cursor-pointer"
                        >
                          <span>Inspect</span>
                          <ExternalLink className="w-3 h-3" />
                        </button>
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          )}

          {/* Surveillance Architecture Overview HUD */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 p-5 rounded-2xl bg-[#090d15] border border-[var(--color-border)]">
            <div className="space-y-1.5">
              <div className="flex items-center gap-2 text-xs font-mono font-bold text-[var(--color-accent)]">
                <SlidersHorizontal className="w-4 h-4" />
                <span>Deterministic Facets</span>
              </div>
              <p className="text-[11px] font-mono text-[var(--color-text-secondary)] leading-relaxed">
                Direct YOLOv8 object classes, chronological start/end frame windows, and detector confidence filtering.
              </p>
            </div>

            <div className="space-y-1.5">
              <div className="flex items-center gap-2 text-xs font-mono font-bold text-cyan-300">
                <Sparkles className="w-4 h-4" />
                <span>Multimodal CLIP Ranking</span>
              </div>
              <p className="text-[11px] font-mono text-[var(--color-text-secondary)] leading-relaxed">
                OpenCLIP ViT-B-32 vector embeddings align natural language visual appearance with stored keyframe crops.
              </p>
            </div>

            <div className="space-y-1.5">
              <div className="flex items-center gap-2 text-xs font-mono font-bold text-emerald-400">
                <Target className="w-4 h-4" />
                <span>ByteTrack Trajectories</span>
              </div>
              <p className="text-[11px] font-mono text-[var(--color-text-secondary)] leading-relaxed">
                Multi-frame identity persistence associates targets across continuous surveillance intervals with motion coordinates.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Add to Case Modal (Phase 7) */}
      <Modal
        isOpen={caseModalOpen}
        onClose={() => setCaseModalOpen(false)}
        title="Add Evidence to Investigation Case"
      >
        {caseSuccessId ? (
          <div className="py-6 text-center space-y-4">
            <div className="w-12 h-12 rounded-full bg-emerald-950/60 border border-emerald-600/60 flex items-center justify-center mx-auto text-emerald-400">
              <Check className="w-6 h-6" />
            </div>
            <div className="space-y-1">
              <h3 className="text-sm font-bold text-white">Evidence Linked Successfully</h3>
              <p className="text-xs text-[var(--color-text-secondary)]">
                The evidence milestone has been added to the case timeline.
              </p>
            </div>
            <div className="flex items-center justify-center gap-2 pt-2">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setCaseModalOpen(false)}
              >
                Close
              </Button>
              <Link to={`/investigations/${caseSuccessId}`}>
                <Button
                  variant="primary"
                  size="sm"
                  className="bg-[var(--color-accent)] text-black font-semibold"
                >
                  <ExternalLink className="w-3.5 h-3.5 mr-1.5" />
                  Open Case Workspace
                </Button>
              </Link>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            {evidenceTarget && (
              <div className="p-3 rounded-lg bg-[var(--color-surface-2)] border border-[var(--color-border)] flex items-center justify-between text-xs font-mono">
                <div>
                  <span className="text-[var(--color-text-muted)] block">TARGET ITEM:</span>
                  <span className="font-bold text-white capitalize">{evidenceTarget.object_class}</span>
                  <span className="text-[var(--color-text-secondary)] ml-2">
                    at {formatDuration(evidenceTarget.timestamp)} ({evidenceTarget.timestamp.toFixed(1)}s)
                  </span>
                </div>
                <div className="text-right">
                  {evidenceTarget.confidence !== undefined && (
                    <span className="text-emerald-400 font-bold block">
                      Conf: {(evidenceTarget.confidence * 100).toFixed(0)}%
                    </span>
                  )}
                  {evidenceTarget.visual_similarity_score !== undefined && evidenceTarget.visual_similarity_score !== null && (
                    <span className="text-[var(--color-accent)] font-bold block">
                      Sim: {(evidenceTarget.visual_similarity_score * 100).toFixed(0)}%
                    </span>
                  )}
                </div>
              </div>
            )}

            <div>
              <label className="block text-xs font-medium text-[var(--color-text-secondary)] mb-1">
                Select Destination Investigation Case
              </label>
              <select
                value={selectedCaseId}
                onChange={(e) => setSelectedCaseId(e.target.value)}
                className="w-full bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-[var(--color-accent)]"
              >
                {availableCases.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.title} ({c.priority.toUpperCase()})
                  </option>
                ))}
                <option value="new">+ Create New Case Dossier...</option>
              </select>
            </div>

            {selectedCaseId === 'new' && (
              <div>
                <label className="block text-xs font-medium text-[var(--color-text-secondary)] mb-1">
                  New Case Title <span className="text-red-400">*</span>
                </label>
                <input
                  type="text"
                  placeholder="e.g. Suspect Sighting North Perimeter"
                  value={newCaseTitle}
                  onChange={(e) => setNewCaseTitle(e.target.value)}
                  className="w-full bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-lg px-3 py-2 text-xs text-white placeholder-[var(--color-text-muted)] focus:outline-none focus:border-[var(--color-accent)]"
                />
              </div>
            )}

            <div>
              <label className="block text-xs font-medium text-[var(--color-text-secondary)] mb-1">
                Investigator Observation Note (Optional)
              </label>
              <textarea
                rows={2}
                placeholder="Observation details, clothing, trajectory notes..."
                value={evidenceNotes}
                onChange={(e) => setEvidenceNotes(e.target.value)}
                className="w-full bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-lg px-3 py-2 text-xs text-white placeholder-[var(--color-text-muted)] focus:outline-none focus:border-[var(--color-accent)] resize-none"
              />
            </div>

            <div className="flex items-center justify-end gap-2 pt-3 border-t border-[var(--color-border)]">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setCaseModalOpen(false)}
              >
                Cancel
              </Button>
              <Button
                variant="primary"
                size="sm"
                onClick={handleConfirmAddToCase}
                disabled={isSubmittingEvidence || (selectedCaseId === 'new' && !newCaseTitle.trim())}
                className="bg-[var(--color-accent)] text-black font-semibold hover:bg-[var(--color-accent-hover)]"
              >
                {isSubmittingEvidence ? (
                  <>
                    <Spinner className="w-3.5 h-3.5 mr-1.5" />
                    Attaching...
                  </>
                ) : (
                  <>
                    <FolderPlus className="w-3.5 h-3.5 mr-1.5" />
                    Attach to Case
                  </>
                )}
              </Button>
            </div>
          </div>
        )}
      </Modal>

      {/* Video Evidence Modal Integration */}
      <VideoPlayerModal
        video={modalVideo}
        isOpen={modalOpen}
        initialTimestamp={seekTarget}
        onClose={() => {
          setModalOpen(false)
          setModalVideo(null)
          setSeekTarget(null)
        }}
      />
    </div>
  )
}
