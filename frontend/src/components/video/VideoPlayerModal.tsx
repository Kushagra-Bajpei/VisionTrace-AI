/**
 * VideoPlayerModal – Enterprise surveillance footage inspector.
 * Features native HTML5 video streaming with HTTP Range 206 support,
 * technical forensic metadata inspection, YOLO object detection & ByteTrack tracking tabs,
 * tactical bounding box keyframe overlays, and seekable track timelines.
 */
import { useEffect, useRef, useState } from 'react'
import {
  Download,
  Trash2,
  Copy,
  Check,
  Maximize2,
  FileVideo,
  Clock,
  Layers,
  Activity,
  Calendar,
  RotateCw,
  Film,
  AlertTriangle,
  Target,
  Crosshair,
  SlidersHorizontal,
  ChevronRight,
  Eye,
  X,
} from 'lucide-react'
import { Modal } from '@/components/ui/Modal'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { videoService } from '@/services/video'
import { authService } from '@/services/auth'
import { formatBytes, formatDuration, formatDateTime, getResolutionLabel } from '@/lib/utils'
import type { Video, ExtractedFrame, ObjectTrack, DetectionEvent } from '@/types'

interface VideoPlayerModalProps {
  video: Video | null
  isOpen: boolean
  onClose: () => void
  onDeleteSuccess?: () => void
  onProcess?: (video: Video) => void
  initialTimestamp?: number | null
}

export function VideoPlayerModal({
  video,
  isOpen,
  onClose,
  onDeleteSuccess,
  onProcess,
  initialTimestamp,
}: VideoPlayerModalProps) {
  const [copiedId, setCopiedId] = useState(false)
  const [isDeleting, setIsDeleting] = useState(false)
  const [isProcessing, setIsProcessing] = useState(false)
  const [frames, setFrames] = useState<ExtractedFrame[]>([])
  const [loadingFrames, setLoadingFrames] = useState(false)
  const [activeTab, setActiveTab] = useState<'telemetry' | 'targets'>('telemetry')
  const [showAnnotations, setShowAnnotations] = useState(true)
  const [tracks, setTracks] = useState<ObjectTrack[]>([])
  const [detections, setDetections] = useState<DetectionEvent[]>([])
  const [selectedClassFilter, setSelectedClassFilter] = useState<string>('all')
  const [selectedTrackId, setSelectedTrackId] = useState<string | null>(null)
  const [selectedFramePreview, setSelectedFramePreview] = useState<{
    frame: ExtractedFrame
    annotatedUrl: string
  } | null>(null)
  const [tokenVideoId, setTokenVideoId] = useState<string | null>(null)
  const [mediaToken, setMediaToken] = useState<string | null>(null)
  const [frameToken, setFrameToken] = useState<string | null>(null)
  const [loadingMedia, setLoadingMedia] = useState<boolean>(true)

  const videoRef = useRef<HTMLVideoElement>(null)

  useEffect(() => {
    if (!isOpen || !video?.id) {
      setMediaToken(null)
      setFrameToken(null)
      setTokenVideoId(null)
      setLoadingMedia(false)
      return
    }

    setLoadingMedia(true)
    setMediaToken(null)
    setFrameToken(null)
    setTokenVideoId(null)

    let isMounted = true

    // Fetch scoped tokens for video and frames
    Promise.allSettled([
      authService.getMediaToken('video', video.id),
      authService.getMediaToken('frame', video.id),
    ]).then(([videoRes, frameRes]) => {
      if (!isMounted) return
      if (videoRes.status === 'fulfilled') {
        setMediaToken(videoRes.value)
        setTokenVideoId(video.id)
      } else {
        setMediaToken(null)
      }
      if (frameRes.status === 'fulfilled') {
        setFrameToken(frameRes.value)
      } else {
        setFrameToken(null)
      }
      setLoadingMedia(false)
    })

    return () => {
      isMounted = false
    }
  }, [isOpen, video?.id])

  useEffect(() => {
    if (initialTimestamp !== undefined && initialTimestamp !== null && videoRef.current) {
      videoRef.current.currentTime = initialTimestamp
    }
  }, [initialTimestamp, isOpen])

  useEffect(() => {
    if (!isOpen || !video?.id) {
      setFrames([])
      setTracks([])
      setDetections([])
      setSelectedTrackId(null)
      setSelectedFramePreview(null)
      return
    }

    // Load extracted keyframes
    if (video.status === 'completed' || video.video_metadata?.extracted_frames_count) {
      setLoadingFrames(true)
      videoService
        .getVideoFrames(video.id)
        .then((data) => setFrames(data))
        .catch(() => setFrames([]))
        .finally(() => setLoadingFrames(false))

      // Load YOLO detections & ByteTrack tracks
      videoService
        .getVideoTracks(video.id)
        .then((t) => {
          setTracks(t)
          if (t.length > 0) {
            setActiveTab('targets') // Automatically spotlight tracking if targets found
          }
        })
        .catch(() => setTracks([]))

      videoService
        .getVideoDetections(video.id)
        .then((d) => setDetections(d))
        .catch(() => setDetections([]))
    }
  }, [isOpen, video?.id, video?.status, video?.video_metadata?.extracted_frames_count])

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (!isOpen || !videoRef.current) return

      // Space to toggle play/pause
      if (e.code === 'Space' && document.activeElement?.tagName !== 'BUTTON') {
        e.preventDefault()
        if (videoRef.current.paused) {
          videoRef.current.play()
        } else {
          videoRef.current.pause()
        }
      }

      // Left / Right arrow keys to jump 5 seconds
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
  }, [isOpen])

  if (!video) return null

  const baseStreamUrl = videoService.getStreamUrl(video.id)
  const isStreamAuthorized = Boolean(mediaToken && tokenVideoId === video.id)
  const streamUrl = isStreamAuthorized
    ? `${baseStreamUrl}?media_token=${encodeURIComponent(mediaToken!)}`
    : undefined

  const handleDownload = async () => {
    if (!video) return
    try {
      const token = isStreamAuthorized && mediaToken
        ? mediaToken
        : await authService.getMediaToken('video', video.id)
      const url = `${baseStreamUrl}?media_token=${encodeURIComponent(token)}`
      const a = document.createElement('a')
      a.href = url
      a.download = video.original_filename
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
    } catch {
      window.open(baseStreamUrl, '_blank')
    }
  }

  const handleCopyId = () => {
    navigator.clipboard.writeText(video.id)
    setCopiedId(true)
    setTimeout(() => setCopiedId(false), 2000)
  }

  const handleDelete = async () => {
    if (!confirm(`Are you sure you want to permanently delete "${video.original_filename}"?`)) {
      return
    }

    setIsDeleting(true)
    try {
      await videoService.deleteVideo(video.id)
      onClose()
      onDeleteSuccess?.()
    } catch (err) {
      setIsDeleting(false)
      alert(err instanceof Error ? err.message : 'Failed to delete video')
    }
  }

  const handleProcess = async () => {
    if (!video || !onProcess) return
    setIsProcessing(true)
    try {
      await onProcess(video)
    } finally {
      setIsProcessing(false)
    }
  }

  const handleSeekToTime = (timestampSeconds: number, trackId?: string) => {
    if (trackId) {
      setSelectedTrackId(trackId)
    }
    if (videoRef.current) {
      videoRef.current.currentTime = timestampSeconds
      videoRef.current.play().catch(() => {})
    }
  }

  // Filtered tracks
  const filteredTracks = selectedClassFilter === 'all'
    ? tracks
    : tracks.filter((t) => t.object_class.toLowerCase() === selectedClassFilter.toLowerCase())

  // Unique detected classes
  const uniqueClasses = Array.from(new Set(tracks.map((t) => t.object_class.toLowerCase())))

  return (
    <>
      <Modal
        isOpen={isOpen}
        onClose={onClose}
        title={video.original_filename}
        subtitle={`UUID: ${video.id}`}
        maxWidth="6xl"
      >
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Left Column: Video Screen & Keyframes (7 cols on desktop) */}
          <div className="lg:col-span-7 flex flex-col space-y-3">
            <div className="relative rounded-xl overflow-hidden bg-black border border-[var(--color-border-2)] aspect-video shadow-2xl flex items-center justify-center group">
              {streamUrl ? (
                <video
                  ref={videoRef}
                  src={streamUrl}
                  controls
                  autoPlay
                  playsInline
                  onLoadedMetadata={() => {
                    if (initialTimestamp !== undefined && initialTimestamp !== null && videoRef.current) {
                      videoRef.current.currentTime = initialTimestamp
                    }
                  }}
                  className="w-full h-full object-contain"
                >
                  Your browser does not support the video tag.
                </video>
              ) : (
                <div className="flex flex-col items-center justify-center gap-3 text-cyan-400 p-6 text-center select-none">
                  <div className="relative flex items-center justify-center">
                    <RotateCw className="w-8 h-8 animate-spin text-[var(--color-accent)] opacity-80" />
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
              <div className="absolute top-3 left-3 flex items-center gap-2 pointer-events-none opacity-85">
                <Badge variant="telemetry">
                  {getResolutionLabel(video.width, video.height)}
                </Badge>
                {video.fps && <Badge variant="telemetry">{video.fps} FPS</Badge>}
                {tracks.length > 0 && (
                  <span className="px-2 py-0.5 rounded bg-cyan-950/80 backdrop-blur-md border border-[var(--color-accent)]/50 text-[10px] font-mono text-[var(--color-accent)] font-bold flex items-center gap-1 shadow-sm">
                    <Target className="w-3 h-3 text-[var(--color-accent)]" />
                    {tracks.length} {tracks.length === 1 ? 'TRACK' : 'TRACKS'}
                  </span>
                )}
              </div>
            </div>

            {/* Quick Player Bar */}
            <div className="flex items-center justify-between px-3 py-2 rounded-lg bg-[var(--color-surface-2)] border border-[var(--color-border)] text-xs font-mono text-[var(--color-text-secondary)]">
              <div className="flex items-center gap-2 sm:gap-3">
                <span className="hidden sm:inline">Shortcuts:</span>
                <kbd className="px-1.5 py-0.5 rounded bg-[var(--color-surface-3)] text-[var(--color-text-primary)] border border-[var(--color-border-2)]">
                  Space
                </kbd>
                <span className="hidden sm:inline">Play/Pause</span>
                <kbd className="px-1.5 py-0.5 rounded bg-[var(--color-surface-3)] text-[var(--color-text-primary)] border border-[var(--color-border-2)]">
                  ← / →
                </kbd>
                <span>5s</span>
              </div>

              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="xs"
                  onClick={handleDownload}
                  disabled={loadingMedia}
                  title="Download surveillance video"
                >
                  <Download className="w-3.5 h-3.5" />
                  <span className="hidden sm:inline">Download</span>
                </Button>
              </div>
            </div>

            {/* Extracted Keyframe Filmstrip with YOLO Overlay Toggle */}
            {frames.length > 0 && (
              <div className="p-3 rounded-xl bg-[var(--color-surface-2)] border border-[var(--color-border)] space-y-2.5">
                <div className="flex items-center justify-between text-xs font-mono">
                  <span className="flex items-center gap-1.5 uppercase font-bold text-[var(--color-text-primary)]">
                    <Film className="w-3.5 h-3.5 text-[var(--color-accent)]" />
                    Forensic Keyframes ({frames.length} @ 1.0 fps)
                  </span>

                  {/* Toggle Bounding Box Overlays */}
                  <button
                    onClick={() => setShowAnnotations(!showAnnotations)}
                    className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px] font-mono border transition-all cursor-pointer ${
                      showAnnotations
                        ? 'bg-cyan-950/60 border-[var(--color-accent)] text-[var(--color-accent)]'
                        : 'bg-[var(--color-surface-3)] border-[var(--color-border)] text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)]'
                    }`}
                    title="Toggle visual bounding boxes and detection tags"
                  >
                    <Crosshair className="w-3 h-3" />
                    <span>YOLO Bounding Boxes: {showAnnotations ? 'ON' : 'OFF'}</span>
                  </button>
                </div>

                <div className="flex items-center gap-2.5 overflow-x-auto pb-1.5 pt-0.5 scrollbar-thin">
                  {frames.map((frame) => {
                    const rawAnnotated = videoService.getAnnotatedFrameUrl(video.id, frame.filename)
                    const annotatedUrl = frameToken ? `${rawAnnotated}?media_token=${encodeURIComponent(frameToken)}` : undefined
                    const rawPreview = frame.preview_url
                    const previewUrl = frameToken ? `${rawPreview}?media_token=${encodeURIComponent(frameToken)}` : undefined
                    const frameImgUrl = showAnnotations ? annotatedUrl : previewUrl

                    return (
                      <button
                        key={frame.index}
                        onClick={() => handleSeekToTime(frame.timestamp_seconds)}
                        onDoubleClick={() => annotatedUrl && setSelectedFramePreview({ frame, annotatedUrl })}
                        className="relative shrink-0 w-28 aspect-video rounded-md overflow-hidden border border-[var(--color-border)] hover:border-[var(--color-accent)] focus:outline-none focus:ring-1 focus:ring-[var(--color-accent)] transition-all group/f cursor-pointer bg-black"
                        title={`Seek to ${frame.timestamp_seconds}s (Double-click to inspect)`}
                      >
                        {frameImgUrl ? (
                          <img
                            src={frameImgUrl}
                            alt={`Frame at ${frame.timestamp_seconds}s`}
                            className="w-full h-full object-cover group-hover/f:scale-105 transition-transform"
                            loading="lazy"
                          />
                        ) : (
                          <div className="w-full h-full flex items-center justify-center bg-[var(--color-surface-2)]">
                            <RotateCw className="w-3.5 h-3.5 text-cyan-400 animate-spin opacity-50" />
                          </div>
                        )}
                        <div className="absolute top-1 right-1 opacity-0 group-hover/f:opacity-100 transition-opacity">
                          <span
                            onClick={(e) => {
                              e.stopPropagation()
                              if (annotatedUrl) {
                                setSelectedFramePreview({ frame, annotatedUrl })
                              }
                            }}
                            className="p-1 rounded bg-black/80 hover:bg-cyan-950 text-[var(--color-accent)] border border-cyan-800/40 inline-flex"
                            title="Inspect high-res annotated frame"
                          >
                            <Eye className="w-3 h-3" />
                          </span>
                        </div>
                        <div className="absolute bottom-0 inset-x-0 bg-black/85 px-1 py-0.5 text-[9px] font-mono font-bold text-center text-white flex items-center justify-between">
                          <span>#{frame.index}</span>
                          <span>{formatDuration(frame.timestamp_seconds)}</span>
                        </div>
                      </button>
                    )
                  })}
                </div>
              </div>
            )}
          </div>

          {/* Right Column: Tabbed Inspector (5 cols on desktop) */}
          <div className="lg:col-span-5 flex flex-col justify-between space-y-3">
            <div className="p-4 rounded-xl bg-[var(--color-surface-2)] border border-[var(--color-border)] space-y-4">
              {/* Tab Selector Header */}
              <div className="flex items-center justify-between border-b border-[var(--color-border)] pb-2.5">
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setActiveTab('telemetry')}
                    className={`px-2.5 py-1 rounded text-xs font-mono font-bold transition-all cursor-pointer ${
                      activeTab === 'telemetry'
                        ? 'bg-[var(--color-surface-3)] text-[var(--color-accent)] border border-cyan-900/40'
                        : 'text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)]'
                    }`}
                  >
                    Technical Telemetry
                  </button>

                  <button
                    onClick={() => setActiveTab('targets')}
                    className={`px-2.5 py-1 rounded text-xs font-mono font-bold transition-all cursor-pointer flex items-center gap-1.5 ${
                      activeTab === 'targets'
                        ? 'bg-[var(--color-surface-3)] text-[var(--color-accent)] border border-cyan-900/40'
                        : 'text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)]'
                    }`}
                  >
                    <Target className="w-3.5 h-3.5" />
                    <span>Targets & Tracks</span>
                    {tracks.length > 0 && (
                      <span className="px-1.5 py-0.2 rounded-full text-[10px] bg-[var(--color-accent)] text-[#05080c] font-black">
                        {tracks.length}
                      </span>
                    )}
                  </button>
                </div>

                <Badge variant={video.status} dot>
                  {video.status === 'processing'
                    ? `Processing ${Math.round(video.processing_progress)}%`
                    : video.status}
                </Badge>
              </div>

              {/* TAB 1: TECHNICAL TELEMETRY */}
              {activeTab === 'telemetry' && (
                <div className="space-y-3">
                  {/* Live Progress Bar if processing */}
                  {video.status === 'processing' && (
                    <div className="space-y-1.5 p-2.5 rounded-lg bg-[var(--color-surface-3)] border border-sky-500/20">
                      <div className="flex items-center justify-between text-[11px] font-mono">
                        <span className="text-sky-300 flex items-center gap-1.5">
                          <RotateCw className="w-3 h-3 animate-spin text-sky-400" />
                          Processing YOLO & ByteTrack...
                        </span>
                        <span className="text-sky-400 font-bold">
                          {Math.round(video.processing_progress)}%
                        </span>
                      </div>
                      <div className="w-full h-1.5 bg-sky-950/60 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-sky-400 transition-all duration-300"
                          style={{ width: `${Math.max(5, video.processing_progress)}%` }}
                        />
                      </div>
                    </div>
                  )}

                  {/* Trigger Button if uploaded but not queued */}
                  {video.status === 'uploaded' && onProcess && (
                    <div className="p-2.5 rounded-lg bg-[var(--color-surface-3)] border border-[var(--color-border)] space-y-2">
                      <p className="text-[11px] font-mono text-[var(--color-text-secondary)]">
                        Staged for background extraction, YOLO detection & ByteTrack.
                      </p>
                      <Button
                        variant="primary"
                        size="xs"
                        onClick={handleProcess}
                        disabled={isProcessing}
                        className="w-full"
                      >
                        <RotateCw
                          className={`w-3.5 h-3.5 mr-1 ${isProcessing ? 'animate-spin' : ''}`}
                        />
                        <span>{isProcessing ? 'Enqueuing…' : 'Start Target Detection Pipeline'}</span>
                      </Button>
                    </div>
                  )}

                  {/* Metadata Rows */}
                  <div className="space-y-2.5 text-xs font-mono">
                    {/* UUID */}
                    <div className="flex flex-col gap-1">
                      <span className="text-[10px] uppercase text-[var(--color-text-muted)]">
                        Asset UUID
                      </span>
                      <div className="flex items-center justify-between p-1.5 rounded bg-[var(--color-surface-3)] border border-[var(--color-border)] text-[11px] text-[var(--color-accent)]">
                        <span className="truncate max-w-[210px]">{video.id}</span>
                        <button
                          onClick={handleCopyId}
                          className="p-1 hover:text-white transition-colors cursor-pointer"
                          title="Copy UUID"
                        >
                          {copiedId ? (
                            <Check className="w-3 h-3 text-emerald-400" />
                          ) : (
                            <Copy className="w-3 h-3" />
                          )}
                        </button>
                      </div>
                    </div>

                    {/* Resolution */}
                    <div className="flex items-center justify-between py-1.5 border-b border-[var(--color-border)]/50">
                      <span className="text-[var(--color-text-secondary)] flex items-center gap-1.5">
                        <Maximize2 className="w-3.5 h-3.5 text-[var(--color-text-muted)]" />
                        Resolution:
                      </span>
                      <span className="text-[var(--color-text-primary)] font-bold">
                        {video.width && video.height
                          ? `${video.width} x ${video.height} (${getResolutionLabel(video.width, video.height)})`
                          : 'Unknown'}
                      </span>
                    </div>

                    {/* Duration */}
                    <div className="flex items-center justify-between py-1.5 border-b border-[var(--color-border)]/50">
                      <span className="text-[var(--color-text-secondary)] flex items-center gap-1.5">
                        <Clock className="w-3.5 h-3.5 text-[var(--color-text-muted)]" />
                        Duration:
                      </span>
                      <span className="text-[var(--color-text-primary)] font-bold">
                        {formatDuration(video.duration)} ({video.duration || 0}s)
                      </span>
                    </div>

                    {/* Frame Rate */}
                    <div className="flex items-center justify-between py-1.5 border-b border-[var(--color-border)]/50">
                      <span className="text-[var(--color-text-secondary)] flex items-center gap-1.5">
                        <Activity className="w-3.5 h-3.5 text-[var(--color-text-muted)]" />
                        Frame Rate:
                      </span>
                      <span className="text-[var(--color-text-primary)] font-bold">
                        {video.fps ? `${video.fps} FPS` : 'Variable'}
                      </span>
                    </div>

                    {/* File Size */}
                    <div className="flex items-center justify-between py-1.5 border-b border-[var(--color-border)]/50">
                      <span className="text-[var(--color-text-secondary)] flex items-center gap-1.5">
                        <FileVideo className="w-3.5 h-3.5 text-[var(--color-text-muted)]" />
                        File Size:
                      </span>
                      <span className="text-[var(--color-text-primary)] font-bold">
                        {formatBytes(video.file_size)}
                      </span>
                    </div>

                    {/* Extracted Keyframes Count */}
                    {video.video_metadata?.extracted_frames_count !== undefined && (
                      <div className="flex items-center justify-between py-1.5 border-b border-[var(--color-border)]/50">
                        <span className="text-[var(--color-text-secondary)] flex items-center gap-1.5">
                          <Film className="w-3.5 h-3.5 text-[var(--color-accent)]" />
                          Forensic Frames:
                        </span>
                        <span className="text-[var(--color-accent)] font-bold">
                          {video.video_metadata.extracted_frames_count} sampled
                        </span>
                      </div>
                    )}

                    {/* Detection Summary */}
                    {video.video_metadata?.tracks_count !== undefined && (
                      <div className="flex items-center justify-between py-1.5 border-b border-[var(--color-border)]/50">
                        <span className="text-[var(--color-text-secondary)] flex items-center gap-1.5">
                          <Target className="w-3.5 h-3.5 text-[var(--color-accent)]" />
                          Tracked Objects:
                        </span>
                        <span className="text-[var(--color-accent)] font-bold">
                          {video.video_metadata.tracks_count} tracks ({video.video_metadata.detections_count || 0} hits)
                        </span>
                      </div>
                    )}

                    {/* Ingest Date */}
                    <div className="flex items-center justify-between py-1.5">
                      <span className="text-[var(--color-text-secondary)] flex items-center gap-1.5">
                        <Calendar className="w-3.5 h-3.5 text-[var(--color-text-muted)]" />
                        Ingested:
                      </span>
                      <span className="text-[var(--color-text-primary)]">
                        {formatDateTime(video.created_at)}
                      </span>
                    </div>
                  </div>
                </div>
              )}

              {/* TAB 2: TARGETS & TRACKS (PHASE 4B) */}
              {activeTab === 'targets' && (
                <div className="space-y-3 text-xs font-mono">
                  {/* Summary Metric Counters */}
                  <div className="grid grid-cols-2 gap-2">
                    <div className="p-2.5 rounded-lg bg-[var(--color-surface-3)] border border-[var(--color-border)]">
                      <span className="text-[10px] text-[var(--color-text-muted)] uppercase block">
                        Unique Tracks
                      </span>
                      <span className="text-lg font-bold text-[var(--color-accent)] font-mono">
                        {tracks.length}
                      </span>
                    </div>
                    <div className="p-2.5 rounded-lg bg-[var(--color-surface-3)] border border-[var(--color-border)]">
                      <span className="text-[10px] text-[var(--color-text-muted)] uppercase block">
                        Total Detections
                      </span>
                      <span className="text-lg font-bold text-white font-mono">
                        {detections.length}
                      </span>
                    </div>
                  </div>

                  {/* Class Filter Bar */}
                  {uniqueClasses.length > 0 && (
                    <div className="space-y-1.5">
                      <span className="text-[10px] text-[var(--color-text-muted)] uppercase flex items-center gap-1">
                        <SlidersHorizontal className="w-3 h-3 text-[var(--color-accent)]" />
                        Filter By Target Class
                      </span>
                      <div className="flex flex-wrap items-center gap-1.5">
                        <button
                          onClick={() => setSelectedClassFilter('all')}
                          className={`px-2 py-0.5 rounded text-[11px] font-mono border transition-all cursor-pointer ${
                            selectedClassFilter === 'all'
                              ? 'bg-[var(--color-accent)] text-[#05080c] font-black border-[var(--color-accent)]'
                              : 'bg-[var(--color-surface-3)] text-[var(--color-text-secondary)] border-[var(--color-border)] hover:text-white'
                          }`}
                        >
                          All ({tracks.length})
                        </button>
                        {uniqueClasses.map((cls) => {
                          const count = tracks.filter(
                            (t) => t.object_class.toLowerCase() === cls,
                          ).length
                          return (
                            <button
                              key={cls}
                              onClick={() => setSelectedClassFilter(cls)}
                              className={`px-2 py-0.5 rounded text-[11px] font-mono border capitalize transition-all cursor-pointer ${
                                selectedClassFilter === cls
                                  ? 'bg-[var(--color-accent)] text-[#05080c] font-black border-[var(--color-accent)]'
                                  : 'bg-[var(--color-surface-3)] text-[var(--color-text-secondary)] border-[var(--color-border)] hover:text-white'
                              }`}
                            >
                              {cls} ({count})
                            </button>
                          )
                        })}
                      </div>
                    </div>
                  )}

                  {/* Chronological Track List */}
                  <div className="space-y-2">
                    <span className="text-[10px] text-[var(--color-text-muted)] uppercase block">
                      Track Directory (Click to Seek)
                    </span>

                    {filteredTracks.length === 0 ? (
                      <div className="p-4 rounded-lg bg-[var(--color-surface-3)] text-center text-[var(--color-text-muted)] text-[11px]">
                        {tracks.length === 0
                          ? 'No objects detected yet. Run target detection pipeline.'
                          : 'No tracks match current class filter.'}
                      </div>
                    ) : (
                      <div className="max-h-60 overflow-y-auto space-y-1.5 pr-1 scrollbar-thin">
                        {filteredTracks.map((trk) => {
                          const isSelected = selectedTrackId === trk.id
                          return (
                            <div
                              key={trk.id}
                              onClick={() => handleSeekToTime(trk.start_time, trk.id)}
                              className={`p-2.5 rounded-lg border transition-all cursor-pointer flex items-center justify-between group ${
                                isSelected
                                  ? 'bg-cyan-950/40 border-[var(--color-accent)] shadow-[0_0_12px_rgba(0,229,255,0.15)]'
                                  : 'bg-[var(--color-surface-3)] border-[var(--color-border)] hover:border-[var(--color-border-accent)]'
                              }`}
                            >
                              <div className="flex items-center gap-2.5">
                                <span className="w-6 h-6 rounded bg-black/60 text-[var(--color-accent)] border border-cyan-800/40 font-bold flex items-center justify-center text-[10px]">
                                  #{trk.track_id}
                                </span>
                                <div>
                                  <div className="flex items-center gap-1.5">
                                    <span className="font-bold text-white capitalize text-[11px]">
                                      {trk.object_class}
                                    </span>
                                    <span className="text-[10px] text-emerald-400 font-semibold">
                                      {Math.round(trk.confidence_avg * 100)}%
                                    </span>
                                  </div>
                                  <span className="text-[10px] text-[var(--color-text-muted)] block">
                                    {formatDuration(trk.start_time)} → {formatDuration(trk.end_time)} ({trk.attributes?.detection_count || 1} hits)
                                  </span>
                                </div>
                              </div>

                              <div className="flex items-center gap-1 text-[var(--color-accent)] opacity-80 group-hover:opacity-100 group-hover:translate-x-0.5 transition-all text-[11px]">
                                <span>Seek</span>
                                <ChevronRight className="w-3.5 h-3.5" />
                              </div>
                            </div>
                          )
                        })}
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>

            {/* Delete Action Bar */}
            <div className="p-4 rounded-xl bg-rose-950/15 border border-rose-500/20 space-y-2">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs font-mono font-bold text-rose-300">Danger Zone</p>
                  <p className="text-[10px] text-rose-400/80">
                    Removes asset, frames, and track records
                  </p>
                </div>
                <Button
                  variant="danger"
                  size="xs"
                  onClick={handleDelete}
                  disabled={isDeleting}
                >
                  <Trash2 className="w-3.5 h-3.5" />
                  <span>{isDeleting ? 'Deleting…' : 'Delete'}</span>
                </Button>
              </div>
            </div>
          </div>
        </div>
      </Modal>

      {/* High-Resolution Tactical Annotated Frame Lightbox */}
      {selectedFramePreview && (
        <div
          className="fixed inset-0 z-50 bg-black/90 backdrop-blur-md flex items-center justify-center p-4"
          onClick={() => setSelectedFramePreview(null)}
        >
          <div
            className="relative max-w-5xl w-full bg-[#080c14] border border-cyan-800/60 rounded-2xl overflow-hidden shadow-2xl p-4 space-y-3"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between pb-2 border-b border-[var(--color-border)]">
              <div className="flex items-center gap-2 text-xs font-mono text-[var(--color-accent)]">
                <Crosshair className="w-4 h-4 text-[var(--color-accent)]" />
                <span className="font-bold">
                  TACTICAL SURVEILLANCE INSPECTOR — FRAME #{selectedFramePreview.frame.index} ({formatDuration(selectedFramePreview.frame.timestamp_seconds)})
                </span>
              </div>
              <button
                onClick={() => setSelectedFramePreview(null)}
                className="p-1 rounded text-[var(--color-text-muted)] hover:text-white hover:bg-white/10 cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="relative aspect-video w-full rounded-lg overflow-hidden bg-black border border-white/10 flex items-center justify-center">
              <img
                src={selectedFramePreview.annotatedUrl}
                alt={`Annotated Frame #${selectedFramePreview.frame.index}`}
                className="w-full h-full object-contain"
              />
            </div>

            <div className="flex items-center justify-between text-xs font-mono text-[var(--color-text-muted)]">
              <span>Cyan/Emerald bounding boxes indicate YOLOv8 + ByteTrack persistent tracks</span>
              <Button
                variant="outline"
                size="xs"
                onClick={() => handleSeekToTime(selectedFramePreview.frame.timestamp_seconds)}
              >
                Seek Player to this Timestamp
              </Button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
