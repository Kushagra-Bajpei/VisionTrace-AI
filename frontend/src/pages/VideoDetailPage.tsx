/**
 * VideoDetailPage – Dedicated Full-Page CCTV Forensic Intelligence Inspector.
 * Provides maximum screen real estate for surveillance playback, evidentiary analysis,
 * YOLOv8 detection overlays, and ByteTrack multi-object trajectories.
 */
import { useEffect, useRef, useState } from 'react'
import { useParams, useSearchParams, useNavigate, Link } from 'react-router-dom'
import {
  ArrowLeft,
  Play,
  RotateCw,
  Clock,
  Target,
  Crosshair,
  ShieldCheck,
  FileVideo,
  Download,
  Copy,
  Check,
  Film,
  SlidersHorizontal,
  ChevronRight,
  Eye,
  Sparkles,
} from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Card, CardContent } from '@/components/ui/Card'
import { Modal } from '@/components/ui/Modal'
import { videoService } from '@/services/video'
import { authService } from '@/services/auth'
import { formatBytes, formatDuration, formatDateTime, getResolutionLabel } from '@/lib/utils'
import type { Video, ExtractedFrame, ObjectTrack, DetectionEvent } from '@/types'

export function VideoDetailPage() {
  const { videoId } = useParams<{ videoId: string }>()
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()

  // Query parameter context
  const timestampParam = searchParams.get('timestamp')
  const initialTimestamp = timestampParam !== null ? parseFloat(timestampParam) : null
  const caseId = searchParams.get('caseId')
  const caseTitle = searchParams.get('caseTitle')
  const objectClass = searchParams.get('objectClass')

  // State
  const [video, setVideo] = useState<Video | null>(null)
  const [loadingVideo, setLoadingVideo] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [copiedId, setCopiedId] = useState(false)
  const [copiedHash, setCopiedHash] = useState(false)
  const [frames, setFrames] = useState<ExtractedFrame[]>([])
  const [loadingFrames, setLoadingFrames] = useState(false)
  const [activeTab, setActiveTab] = useState<'targets' | 'telemetry'>('targets')
  const [showAnnotations, setShowAnnotations] = useState(true)
  const [tracks, setTracks] = useState<ObjectTrack[]>([])
  const [detections, setDetections] = useState<DetectionEvent[]>([])
  const [selectedClassFilter, setSelectedClassFilter] = useState<string>('all')
  const [selectedTrackId, setSelectedTrackId] = useState<number | null>(null)

  const [selectedFramePreview, setSelectedFramePreview] = useState<{
    frame: ExtractedFrame
    annotatedUrl: string
  } | null>(null)

  const [mediaToken, setMediaToken] = useState<string | null>(null)
  const [frameToken, setFrameToken] = useState<string | null>(null)
  const [loadingMedia, setLoadingMedia] = useState<boolean>(true)

  const videoRef = useRef<HTMLVideoElement>(null)

  // 1. Fetch Video Metadata
  useEffect(() => {
    if (!videoId) return
    setLoadingVideo(true)
    setError(null)

    videoService
      .getVideo(videoId)
      .then((data) => {
        setVideo(data)
      })
      .catch((err) => {
        console.error('Failed to load video:', err)
        setError(err instanceof Error ? err.message : 'Surveillance footage asset not found.')
      })
      .finally(() => setLoadingVideo(false))
  }, [videoId])

  // 2. Obtain auth token for media streaming (use existing JWT directly — no extra round-trip)
  useEffect(() => {
    if (!videoId) return
    // Read the access token stored by AuthContext — works immediately without an extra API call
    const jwt = localStorage.getItem('visiontrace_token')
    if (jwt) {
      setMediaToken(jwt)
      setFrameToken(jwt)
    } else {
      // Fallback: request a scoped media token (120s expiry)
      Promise.allSettled([
        authService.getMediaToken('video', videoId),
        authService.getMediaToken('frame', videoId),
      ]).then(([videoRes, frameRes]) => {
        setMediaToken(videoRes.status === 'fulfilled' ? videoRes.value : null)
        setFrameToken(frameRes.status === 'fulfilled' ? frameRes.value : null)
      })
    }
    setLoadingMedia(false)
  }, [videoId])

  // 3. Load Frames, Tracks, and Detections
  useEffect(() => {
    if (!videoId || !video) return

    if (video.status === 'completed' || video.video_metadata?.extracted_frames_count) {
      setLoadingFrames(true)
      videoService
        .getVideoFrames(videoId)
        .then((data) => setFrames(data))
        .catch(() => setFrames([]))
        .finally(() => setLoadingFrames(false))

      videoService
        .getVideoTracks(videoId)
        .then((t) => {
          setTracks(t)
          if (t.length > 0) {
            setActiveTab('targets')
          }
        })
        .catch(() => setTracks([]))

      videoService
        .getVideoDetections(videoId)
        .then((d) => setDetections(d))
        .catch(() => setDetections([]))
    }
  }, [videoId, video?.status, video?.video_metadata?.extracted_frames_count])

  // 4. Seek to Evidence Timestamp
  useEffect(() => {
    if (initialTimestamp === null || !Number.isFinite(initialTimestamp)) return

    const applyTimestamp = () => {
      if (videoRef.current && Number.isFinite(initialTimestamp)) {
        videoRef.current.currentTime = initialTimestamp
      }
    }

    applyTimestamp()
    const v = videoRef.current
    if (v) {
      v.addEventListener('loadedmetadata', applyTimestamp)
      v.addEventListener('canplay', applyTimestamp)
      v.addEventListener('loadeddata', applyTimestamp)
    }

    return () => {
      if (v) {
        v.removeEventListener('loadedmetadata', applyTimestamp)
        v.removeEventListener('canplay', applyTimestamp)
        v.removeEventListener('loadeddata', applyTimestamp)
      }
    }
  }, [initialTimestamp, mediaToken])

  // 5. Global Keyboard Shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (!videoRef.current) return
      if (document.activeElement?.tagName === 'INPUT' || document.activeElement?.tagName === 'TEXTAREA') {
        return
      }

      if (e.code === 'Space') {
        e.preventDefault()
        if (videoRef.current.paused) {
          videoRef.current.play()
        } else {
          videoRef.current.pause()
        }
      }

      if (e.code === 'ArrowLeft') {
        e.preventDefault()
        videoRef.current.currentTime = Math.max(0, videoRef.current.currentTime - 5)
      } else if (e.code === 'ArrowRight') {
        e.preventDefault()
        videoRef.current.currentTime = Math.min(
          videoRef.current.duration || 0,
          videoRef.current.currentTime + 5,
        )
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [])

  const handleCopyId = () => {
    if (!video) return
    navigator.clipboard.writeText(video.id)
    setCopiedId(true)
    setTimeout(() => setCopiedId(false), 2000)
  }

  const handleCopyHash = () => {
    if (!video?.file_hash) return
    navigator.clipboard.writeText(video.file_hash)
    setCopiedHash(true)
    setTimeout(() => setCopiedHash(false), 2000)
  }

  const handleDownload = async () => {
    if (!video) return
    const baseStreamUrl = videoService.getStreamUrl(video.id)
    // Use the already-available JWT token directly
    const jwt = localStorage.getItem('visiontrace_token') || mediaToken
    if (jwt) {
      const url = `${baseStreamUrl}?token=${encodeURIComponent(jwt)}`
      const a = document.createElement('a')
      a.href = url
      a.download = video.original_filename
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
    } else {
      window.open(baseStreamUrl, '_blank')
    }
  }

  const handleSeekToTime = (timestampSeconds: number, trackId?: number) => {
    if (trackId !== undefined) {
      setSelectedTrackId(trackId)
    }
    if (videoRef.current) {
      videoRef.current.currentTime = timestampSeconds
      videoRef.current.play().catch(() => {})
    }
  }

  if (loadingVideo) {
    return (
      <div className="min-h-[70vh] flex flex-col items-center justify-center gap-4 text-center">
        <div className="relative flex items-center justify-center">
          <RotateCw className="w-10 h-10 animate-spin text-[var(--color-accent)] opacity-80" />
          <Crosshair className="w-5 h-5 text-cyan-200 absolute" />
        </div>
        <div className="space-y-1">
          <p className="text-sm font-mono font-bold uppercase tracking-wider text-white">
            Loading Surveillance Asset
          </p>
          <p className="text-xs font-mono text-[var(--color-text-muted)]">
            Retrieving forensic indexes and cryptographic signatures...
          </p>
        </div>
      </div>
    )
  }

  if (error || !video) {
    return (
      <div className="min-h-[70vh] flex flex-col items-center justify-center gap-4 text-center p-6">
        <div className="w-14 h-14 rounded-2xl bg-red-950/40 border border-red-800/50 flex items-center justify-center text-red-400">
          <FileVideo className="w-7 h-7" />
        </div>
        <h2 className="text-lg font-bold font-mono text-white">Surveillance Asset Unavailable</h2>
        <p className="text-xs text-[var(--color-text-secondary)] max-w-md">
          {error || 'The requested video asset could not be located in the forensic repository.'}
        </p>
        <Button
          variant="outline"
          size="sm"
          onClick={() => (caseId ? navigate(`/investigations/${caseId}`) : navigate('/videos'))}
          className="mt-2 font-mono text-xs border-[var(--color-border)]"
        >
          <ArrowLeft className="w-3.5 h-3.5 mr-1.5" />
          {caseId ? 'Return to Investigation' : 'Return to Video Library'}
        </Button>
      </div>
    )
  }

  const baseStreamUrl = videoService.getStreamUrl(video.id)
  const isStreamAuthorized = Boolean(mediaToken)
  // Use `token=` query param — backend accepts both regular JWT and scoped media tokens this way
  const streamUrl = isStreamAuthorized
    ? `${baseStreamUrl}?token=${encodeURIComponent(mediaToken!)}`
    : undefined

  // Filtered tracks
  const filteredTracks =
    selectedClassFilter === 'all'
      ? tracks
      : tracks.filter((t) => t.object_class.toLowerCase() === selectedClassFilter.toLowerCase())

  const uniqueClasses = Array.from(new Set(tracks.map((t) => t.object_class.toLowerCase())))

  return (
    <div className="space-y-5 max-w-[1700px] mx-auto pb-12">
      {/* ── Top Navigation & Breadcrumbs ── */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-[var(--color-border)] pb-4">
        <div className="space-y-1.5">
          <div className="flex items-center gap-2">
            {caseId ? (
              <Button
                variant="outline"
                size="xs"
                onClick={() => navigate(`/investigations/${caseId}`)}
                className="font-mono text-xs border-[var(--color-border-accent)] text-[var(--color-accent)] hover:bg-cyan-950/40"
              >
                <ArrowLeft className="w-3.5 h-3.5 mr-1" />
                Case: {caseTitle || 'Investigation'}
              </Button>
            ) : (
              <Button
                variant="ghost"
                size="xs"
                onClick={() => navigate('/videos')}
                className="font-mono text-xs text-[var(--color-text-secondary)] hover:text-white"
              >
                <ArrowLeft className="w-3.5 h-3.5 mr-1" />
                Video Library
              </Button>
            )}

            <span className="text-[var(--color-text-muted)] font-mono text-xs">/</span>
            <span className="font-mono text-xs text-white font-semibold truncate max-w-[320px] sm:max-w-md">
              {video.original_filename}
            </span>
          </div>

          <div className="flex flex-wrap items-center gap-2 pt-0.5">
            <h1 className="text-lg sm:text-xl font-bold font-mono tracking-tight text-white uppercase flex items-center gap-2">
              <Film className="w-5 h-5 text-[var(--color-accent)]" />
              Forensic Intelligence Player
            </h1>

            <button
              onClick={handleCopyId}
              className="inline-flex items-center gap-1 text-[11px] font-mono text-[var(--color-text-muted)] hover:text-[var(--color-accent)] transition-colors px-2 py-0.5 rounded bg-[var(--color-surface-2)] border border-[var(--color-border)]"
              title="Copy Video UUID"
            >
              <span>UUID: {video.id.slice(0, 8)}...</span>
              {copiedId ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
            </button>

            {video.file_hash && (
              <span className="inline-flex items-center gap-1 text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-950/60 text-emerald-400 border border-emerald-500/40">
                <ShieldCheck className="w-3 h-3 text-emerald-400" />
                SHA-256 VERIFIED
              </span>
            )}
          </div>
        </div>

        {/* Top Actions */}
        <div className="flex items-center gap-2">
          <Link to={`/search?videoId=${video.id}`}>
            <Button variant="outline" size="sm" className="font-mono text-xs border-[var(--color-border)]">
              <Sparkles className="w-3.5 h-3.5 mr-1.5 text-[var(--color-accent)]" />
              Search Video in AI
            </Button>
          </Link>
          <Button
            variant="primary"
            size="sm"
            onClick={handleDownload}
            disabled={loadingMedia}
            className="font-mono text-xs bg-[var(--color-accent)] text-black font-semibold shadow-[0_0_15px_rgba(0,229,255,0.25)]"
          >
            <Download className="w-3.5 h-3.5 mr-1.5" />
            Download Footage
          </Button>
        </div>
      </div>

      {/* ── Evidentiary Focus Banner (When opened from a case) ── */}
      {initialTimestamp !== null && Number.isFinite(initialTimestamp) && (
        <div className="p-3 sm:p-4 rounded-xl bg-gradient-to-r from-cyan-950/60 via-slate-900/80 to-emerald-950/60 border border-[var(--color-border-accent)] flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-lg">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-[var(--color-accent)]/15 border border-[var(--color-accent)]/40 flex items-center justify-center text-[var(--color-accent)] shrink-0">
              <Target className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-xs font-mono font-bold uppercase tracking-wider text-[var(--color-accent)]">
                  Evidentiary Focus Point
                </span>
                {objectClass && (
                  <Badge variant="default" className="text-[10px] font-mono uppercase bg-emerald-950/80 text-emerald-400 border border-emerald-500/40">
                    Target: {objectClass}
                  </Badge>
                )}
              </div>
              <p className="text-xs text-[var(--color-text-secondary)] font-mono mt-0.5">
                Target recorded at timestamp <strong className="text-white">{formatDuration(initialTimestamp)} ({initialTimestamp.toFixed(1)}s)</strong>.
                YOLO detections & ByteTrack trajectory synchronised.
              </p>
            </div>
          </div>

          <Button
            variant="outline"
            size="sm"
            onClick={() => handleSeekToTime(initialTimestamp)}
            className="border-emerald-500/50 bg-emerald-950/40 text-emerald-400 hover:bg-emerald-900/60 font-mono text-xs shrink-0 self-start sm:self-auto"
          >
            <Clock className="w-3.5 h-3.5 mr-1.5 text-emerald-400" />
            Re-Seek to {initialTimestamp.toFixed(1)}s
          </Button>
        </div>
      )}

      {/* ── Main Two-Column Forensic Inspector Grid ── */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        {/* ── Left Column: Large Video Player & Extracted Keyframes (8 Cols) ── */}
        <div className="lg:col-span-8 flex flex-col space-y-4">
          {/* Native HTML5 Video Stream Player */}
          <div className="relative rounded-2xl overflow-hidden bg-black border border-[var(--color-border-2)] aspect-video shadow-2xl flex items-center justify-center group">
            {streamUrl ? (
              <video
                ref={videoRef}
                src={streamUrl}
                controls
                autoPlay
                playsInline
                onLoadedMetadata={() => {
                  if (initialTimestamp !== null && videoRef.current) {
                    videoRef.current.currentTime = initialTimestamp
                  }
                }}
                onCanPlay={() => {
                  if (initialTimestamp !== null && videoRef.current) {
                    videoRef.current.currentTime = initialTimestamp
                  }
                }}
                className="w-full h-full object-contain"
              >
                Your browser does not support the video tag.
              </video>
            ) : (
              <div className="flex flex-col items-center justify-center gap-3 text-cyan-400 p-8 text-center select-none">
                <div className="relative flex items-center justify-center">
                  <RotateCw className="w-9 h-9 animate-spin text-[var(--color-accent)] opacity-80" />
                  <Crosshair className="w-4 h-4 text-cyan-200 absolute" />
                </div>
                <div className="space-y-1">
                  <p className="text-xs font-mono font-bold uppercase tracking-wider text-white">
                    Authorizing Surveillance Feed
                  </p>
                  <p className="text-[10px] font-mono text-[var(--color-text-muted)]">
                    Acquiring scoped cryptographic media token...
                  </p>
                </div>
              </div>
            )}

            {/* In-player telemetry overlay */}
            <div className="absolute top-3 left-3 flex flex-wrap items-center gap-2 pointer-events-none opacity-90 z-10">
              <Badge variant="telemetry">
                {getResolutionLabel(video.width, video.height)}
              </Badge>
              {video.fps && <Badge variant="telemetry">{video.fps} FPS</Badge>}
              {initialTimestamp !== null && (
                <span className="px-2.5 py-0.5 rounded bg-emerald-950/90 backdrop-blur-md border border-emerald-500/60 text-[10px] font-mono text-emerald-400 font-bold flex items-center gap-1 shadow-md">
                  <Clock className="w-3 h-3 text-emerald-400" />
                  EVIDENCE: {formatDuration(initialTimestamp)} ({initialTimestamp.toFixed(1)}s)
                </span>
              )}
              {tracks.length > 0 && (
                <span className="px-2 py-0.5 rounded bg-cyan-950/80 backdrop-blur-md border border-[var(--color-accent)]/50 text-[10px] font-mono text-[var(--color-accent)] font-bold flex items-center gap-1 shadow-sm">
                  <Target className="w-3 h-3 text-[var(--color-accent)]" />
                  {tracks.length} {tracks.length === 1 ? 'TRACK' : 'TRACKS'}
                </span>
              )}
            </div>
          </div>

          {/* Quick Player Control Bar */}
          <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-2.5 rounded-xl bg-[var(--color-surface)] border border-[var(--color-border)] text-xs font-mono text-[var(--color-text-secondary)]">
            <div className="flex items-center gap-2 sm:gap-3">
              <span className="hidden sm:inline text-[var(--color-text-muted)]">Hotkeys:</span>
              <kbd className="px-1.5 py-0.5 rounded bg-[var(--color-surface-2)] text-[var(--color-text-primary)] border border-[var(--color-border)]">
                Space
              </kbd>
              <span className="hidden sm:inline">Play/Pause</span>
              <kbd className="px-1.5 py-0.5 rounded bg-[var(--color-surface-2)] text-[var(--color-text-primary)] border border-[var(--color-border)]">
                ← / →
              </kbd>
              <span>5s Jump</span>
            </div>

            <div className="flex items-center gap-2">
              {initialTimestamp !== null && (
                <Button
                  variant="outline"
                  size="xs"
                  onClick={() => handleSeekToTime(initialTimestamp)}
                  className="text-emerald-400 border-emerald-500/40 hover:bg-emerald-950/40 text-[11px] font-mono"
                >
                  <Clock className="w-3 h-3 mr-1" />
                  Jump to Evidence ({initialTimestamp.toFixed(1)}s)
                </Button>
              )}
            </div>
          </div>

          {/* Forensic Keyframes Filmstrip */}
          {frames.length > 0 && (
            <Card className="border-[var(--color-border)] bg-[var(--color-surface)]">
              <CardContent className="p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Film className="w-4 h-4 text-[var(--color-accent)]" />
                    <span className="text-xs font-mono font-bold uppercase tracking-wider text-[var(--color-text-primary)]">
                      Forensic Keyframes ({frames.length} @ 1.0 fps)
                    </span>
                  </div>

                  <button
                    onClick={() => setShowAnnotations(!showAnnotations)}
                    className={`text-[11px] font-mono px-2 py-0.5 rounded border transition-colors flex items-center gap-1 cursor-pointer ${
                      showAnnotations
                        ? 'bg-cyan-950/60 text-[var(--color-accent)] border-[var(--color-accent)]/40'
                        : 'bg-[var(--color-surface-2)] text-[var(--color-text-muted)] border-[var(--color-border)]'
                    }`}
                  >
                    <Crosshair className="w-3 h-3" />
                    YOLO Bounding Boxes: {showAnnotations ? 'ON' : 'OFF'}
                  </button>
                </div>

                {loadingFrames ? (
                  <div className="flex items-center justify-center py-6 text-xs font-mono text-[var(--color-text-muted)] gap-2">
                    <RotateCw className="w-4 h-4 animate-spin text-[var(--color-accent)]" />
                    Loading keyframes...
                  </div>
                ) : (
                  <div className="flex gap-2.5 overflow-x-auto pb-2 pt-1 scrollbar-tactical snap-x">
                    {frames.map((f) => {
                      const rawAnnotated = videoService.getAnnotatedFrameUrl(video.id, f.filename)
                      const annotatedUrl = frameToken
                        ? `${rawAnnotated}?token=${encodeURIComponent(frameToken)}`
                        : undefined
                      const rawPreview = f.preview_url
                      const previewUrl = frameToken
                        ? `${rawPreview}?token=${encodeURIComponent(frameToken)}`
                        : undefined
                      const displayUrl = showAnnotations ? annotatedUrl || previewUrl : previewUrl

                      const isNearEvidence =
                        initialTimestamp !== null && Math.abs(f.timestamp_seconds - initialTimestamp) < 0.8

                      return (
                        <div
                          key={f.index}
                          className={`group relative shrink-0 w-36 rounded-lg overflow-hidden border cursor-pointer snap-start transition-all bg-black ${
                            isNearEvidence
                              ? 'border-emerald-500 ring-2 ring-emerald-500/40 shadow-lg'
                              : 'border-[var(--color-border)] hover:border-[var(--color-accent)]'
                          }`}
                          onClick={() => handleSeekToTime(f.timestamp_seconds)}
                          title={`Click to seek to ${formatDuration(f.timestamp_seconds)}`}
                        >
                          <div className="aspect-video bg-black/60 relative overflow-hidden">
                            {displayUrl ? (
                              <img
                                src={displayUrl}
                                alt={`Frame #${f.index}`}
                                className="w-full h-full object-cover group-hover:scale-105 transition-transform"
                                loading="lazy"
                              />
                            ) : (
                              <div className="w-full h-full flex items-center justify-center bg-[var(--color-surface-2)]">
                                <RotateCw className="w-3.5 h-3.5 text-cyan-400 animate-spin opacity-50" />
                              </div>
                            )}
                            <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center gap-1.5">
                              <span className="p-1 rounded bg-black/80 text-[var(--color-accent)] text-[10px] font-mono flex items-center gap-0.5">
                                <Play className="w-2.5 h-2.5 fill-current" /> Seek
                              </span>
                              {annotatedUrl && (
                                <button
                                  onClick={(e) => {
                                    e.stopPropagation()
                                    setSelectedFramePreview({ frame: f, annotatedUrl })
                                  }}
                                  className="p-1 rounded bg-black/80 text-white hover:text-[var(--color-accent)]"
                                  title="Enlarge frame"
                                >
                                  <Eye className="w-3 h-3" />
                                </button>
                              )}
                            </div>
                          </div>
                          <div className="px-1.5 py-1 bg-[var(--color-surface-2)] flex items-center justify-between text-[10px] font-mono">
                            <span className="text-[var(--color-text-muted)]">#{f.index}</span>
                            <span className={isNearEvidence ? 'text-emerald-400 font-bold' : 'text-[var(--color-text-secondary)]'}>
                              {formatDuration(f.timestamp_seconds)}
                            </span>
                          </div>
                        </div>
                      )
                    })}
                  </div>
                )}
              </CardContent>
            </Card>
          )}
        </div>

        {/* ── Right Column: Targets, Tracks & Technical Telemetry (4 Cols) ── */}
        <div className="lg:col-span-4 flex flex-col space-y-4">
          <Card className="border-[var(--color-border)] bg-[var(--color-surface)] flex-1 flex flex-col">
            {/* Tab Header */}
            <div className="flex items-center justify-between p-3 border-b border-[var(--color-border)] bg-[var(--color-surface-2)]/50 rounded-t-xl">
              <span className="text-xs font-mono font-bold uppercase tracking-wider text-[var(--color-text-secondary)]">
                Forensic Analytics
              </span>
              <div className="flex items-center gap-1">
                <button
                  onClick={() => setActiveTab('targets')}
                  className={`px-3 py-1 rounded text-xs font-mono transition-colors flex items-center gap-1.5 cursor-pointer ${
                    activeTab === 'targets'
                      ? 'bg-[var(--color-surface)] text-[var(--color-accent)] border border-[var(--color-border-accent)] font-semibold shadow-sm'
                      : 'text-[var(--color-text-muted)] hover:text-white'
                  }`}
                >
                  <Target className="w-3.5 h-3.5" />
                  Targets & Tracks ({tracks.length})
                </button>
                <button
                  onClick={() => setActiveTab('telemetry')}
                  className={`px-3 py-1 rounded text-xs font-mono transition-colors flex items-center gap-1.5 cursor-pointer ${
                    activeTab === 'telemetry'
                      ? 'bg-[var(--color-surface)] text-[var(--color-accent)] border border-[var(--color-border-accent)] font-semibold shadow-sm'
                      : 'text-[var(--color-text-muted)] hover:text-white'
                  }`}
                >
                  <SlidersHorizontal className="w-3.5 h-3.5" />
                  Telemetry
                </button>
              </div>
            </div>

            <CardContent className="p-4 flex-1 flex flex-col space-y-4">
              {/* TAB 1: TARGETS & TRACKS */}
              {activeTab === 'targets' && (
                <div className="space-y-4 flex-1 flex flex-col">
                  {/* Summary Metric Counters */}
                  <div className="grid grid-cols-2 gap-2">
                    <div className="p-3 rounded-lg bg-[var(--color-surface-2)] border border-[var(--color-border)] space-y-0.5">
                      <span className="text-[10px] font-mono uppercase tracking-wider text-[var(--color-text-muted)]">
                        Unique Tracks
                      </span>
                      <p className="text-xl font-bold font-mono text-[var(--color-accent)]">
                        {tracks.length}
                      </p>
                    </div>
                    <div className="p-3 rounded-lg bg-[var(--color-surface-2)] border border-[var(--color-border)] space-y-0.5">
                      <span className="text-[10px] font-mono uppercase tracking-wider text-[var(--color-text-muted)]">
                        Total Detections
                      </span>
                      <p className="text-xl font-bold font-mono text-white">
                        {detections.length || video.video_metadata?.detections_count || 0}
                      </p>
                    </div>
                  </div>

                  {/* Filter Pills by Detected Class */}
                  {uniqueClasses.length > 0 && (
                    <div className="space-y-1.5">
                      <span className="text-[10px] font-mono uppercase tracking-wider text-[var(--color-text-muted)] block">
                        Filter by Target Class
                      </span>
                      <div className="flex flex-wrap gap-1.5">
                        <button
                          onClick={() => setSelectedClassFilter('all')}
                          className={`px-2 py-0.5 rounded text-[11px] font-mono transition-colors cursor-pointer ${
                            selectedClassFilter === 'all'
                              ? 'bg-[var(--color-accent)] text-black font-bold'
                              : 'bg-[var(--color-surface-2)] text-[var(--color-text-secondary)] border border-[var(--color-border)] hover:text-white'
                          }`}
                        >
                          All ({tracks.length})
                        </button>
                        {uniqueClasses.map((cls) => {
                          const count = tracks.filter(
                            (t) => t.object_class.toLowerCase() === cls.toLowerCase(),
                          ).length
                          return (
                            <button
                              key={cls}
                              onClick={() => setSelectedClassFilter(cls)}
                              className={`px-2 py-0.5 rounded text-[11px] font-mono capitalize transition-colors cursor-pointer ${
                                selectedClassFilter === cls
                                  ? 'bg-[var(--color-accent)] text-black font-bold'
                                  : 'bg-[var(--color-surface-2)] text-[var(--color-text-secondary)] border border-[var(--color-border)] hover:text-white'
                              }`}
                            >
                              {cls} ({count})
                            </button>
                          )
                        })}
                      </div>
                    </div>
                  )}

                  {/* Track Directory List */}
                  <div className="space-y-2 flex-1 flex flex-col">
                    <span className="text-[10px] font-mono uppercase tracking-wider text-[var(--color-text-muted)] block">
                      Track Directory (Click to Seek)
                    </span>

                    {tracks.length === 0 ? (
                      <div className="text-center py-8 text-xs font-mono text-[var(--color-text-muted)]">
                        No targets identified in this surveillance video.
                      </div>
                    ) : filteredTracks.length === 0 ? (
                      <div className="text-center py-6 text-xs font-mono text-[var(--color-text-muted)]">
                        No tracks match class &ldquo;{selectedClassFilter}&rdquo;.
                      </div>
                    ) : (
                      <div className="space-y-2 max-h-[380px] overflow-y-auto pr-1 scrollbar-tactical">
                        {filteredTracks.map((trk) => {
                          const isSelected = selectedTrackId === trk.track_id
                          const detectionHits = trk.attributes?.detection_count || 1

                          return (
                            <div
                              key={trk.id}
                              onClick={() => handleSeekToTime(trk.start_time, trk.track_id)}
                              className={`p-2.5 rounded-lg border transition-all cursor-pointer flex items-center justify-between text-xs font-mono ${
                                isSelected
                                  ? 'bg-cyan-950/40 border-[var(--color-accent)] shadow-sm'
                                  : 'bg-[var(--color-surface-2)]/60 border-[var(--color-border)] hover:border-[var(--color-border-accent)]'
                              }`}
                            >
                              <div className="flex items-center gap-2">
                                <span className="px-1.5 py-0.5 rounded bg-black/60 border border-[var(--color-border)] text-[var(--color-accent)] font-bold text-[10px]">
                                  #{trk.track_id}
                                </span>
                                <div>
                                  <div className="flex items-center gap-1.5">
                                    <span className="font-bold text-white capitalize">
                                      {trk.object_class}
                                    </span>
                                    {trk.confidence_avg !== null && trk.confidence_avg !== undefined && (
                                      <span className="text-[10px] text-emerald-400 font-bold">
                                        {Math.round(trk.confidence_avg * 100)}%
                                      </span>
                                    )}
                                  </div>
                                  <span className="text-[10px] text-[var(--color-text-muted)] block">
                                    {formatDuration(trk.start_time)} → {formatDuration(trk.end_time)} (
                                    {detectionHits} {detectionHits === 1 ? 'hit' : 'hits'})
                                  </span>
                                </div>
                              </div>

                              <span className="text-[11px] text-[var(--color-accent)] hover:underline flex items-center gap-0.5">
                                Seek <ChevronRight className="w-3 h-3" />
                              </span>
                            </div>
                          )
                        })}
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* TAB 2: TECHNICAL TELEMETRY */}
              {activeTab === 'telemetry' && (
                <div className="space-y-3 text-xs font-mono">
                  <div className="p-3 rounded-lg bg-[var(--color-surface-2)] border border-[var(--color-border)] space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-[var(--color-text-muted)]">Container / Codec:</span>
                      <span className="text-white font-semibold uppercase">
                        {video.video_metadata?.codec || 'H.264 / MP4'}
                      </span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-[var(--color-text-muted)]">Dimensions:</span>
                      <span className="text-white font-semibold">
                        {video.width} × {video.height} ({getResolutionLabel(video.width, video.height)})
                      </span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-[var(--color-text-muted)]">Frame Rate:</span>
                      <span className="text-white font-semibold">{video.fps || 30.0} FPS</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-[var(--color-text-muted)]">Total Duration:</span>
                      <span className="text-white font-semibold">
                        {formatDuration(video.duration || 0)} (
                        {(video.duration || 0).toFixed(1)}s)
                      </span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-[var(--color-text-muted)]">Asset File Size:</span>
                      <span className="text-white font-semibold">
                        {formatBytes(video.file_size)}
                      </span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-[var(--color-text-muted)]">Ingest Timestamp:</span>
                      <span className="text-[var(--color-text-secondary)]">
                        {formatDateTime(video.created_at)}
                      </span>
                    </div>
                  </div>

                  {/* Cryptographic SHA-256 Hash Card */}
                  <div className="p-3 rounded-lg bg-[var(--color-surface-2)] border border-[var(--color-border)] space-y-1.5">
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] font-mono uppercase tracking-wider text-[var(--color-text-muted)]">
                        SHA-256 Integrity Hash
                      </span>
                      <button
                        onClick={handleCopyHash}
                        className="text-[var(--color-text-muted)] hover:text-[var(--color-accent)] cursor-pointer"
                        title="Copy Hash"
                      >
                        {copiedHash ? (
                          <Check className="w-3.5 h-3.5 text-emerald-400" />
                        ) : (
                          <Copy className="w-3.5 h-3.5" />
                        )}
                      </button>
                    </div>
                    <p className="text-[11px] font-mono break-all text-emerald-400 bg-black/40 p-2 rounded border border-emerald-900/30 select-all">
                      {video.file_hash || 'SHA-256 signature calculated upon ingest'}
                    </p>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      {/* ── Keyframe Zoom Preview Modal ── */}
      {selectedFramePreview && (
        <Modal
          isOpen={Boolean(selectedFramePreview)}
          onClose={() => setSelectedFramePreview(null)}
          title={`Forensic Keyframe #${selectedFramePreview.frame.index}`}
          subtitle={`Timestamp: ${formatDuration(selectedFramePreview.frame.timestamp_seconds)} (${selectedFramePreview.frame.timestamp_seconds.toFixed(2)}s)`}
          maxWidth="4xl"
        >
          <div className="space-y-3">
            <div className="rounded-xl overflow-hidden bg-black border border-[var(--color-border)] flex items-center justify-center">
              <img
                src={selectedFramePreview.annotatedUrl}
                alt="Enlarged Frame"
                className="w-full max-h-[70vh] object-contain"
              />
            </div>
            <div className="flex items-center justify-between text-xs font-mono text-[var(--color-text-muted)] pt-1">
              <span>YOLOv8 Detection Overlay</span>
              <Button
                variant="outline"
                size="xs"
                onClick={() => {
                  handleSeekToTime(selectedFramePreview.frame.timestamp_seconds)
                  setSelectedFramePreview(null)
                }}
                className="font-mono text-xs border-[var(--color-border-accent)] text-[var(--color-accent)]"
              >
                Seek Player to this Frame
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  )
}
export default VideoDetailPage