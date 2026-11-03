/**
 * VideoCard – High-density tactical CCTV video card.
 * Presents 16:9 thumbnail, duration pill, technical tags, and instant play trigger.
 */
import { useState } from 'react'
import { Play, MoreVertical, Download, Trash2, Maximize2, FileVideo, RotateCw, Target } from 'lucide-react'
import { Badge } from '@/components/ui/Badge'
import { videoService } from '@/services/video'
import { authService } from '@/services/auth'
import { formatBytes, formatDuration, formatRelativeTime, getResolutionLabel } from '@/lib/utils'
import type { Video } from '@/types'

interface VideoCardProps {
  video: Video
  onPlay: (video: Video) => void
  onDelete: (video: Video) => void
  onProcess?: (video: Video) => void
}

export function VideoCard({ video, onPlay, onDelete, onProcess }: VideoCardProps) {
  const [menuOpen, setMenuOpen] = useState(false)
  const [thumbError, setThumbError] = useState(false)

  const thumbnailUrl = video.thumbnail_path
    ? videoService.getThumbnailUrl(video.id)
    : null

  const handleDownload = async (e: React.MouseEvent) => {
    e.stopPropagation()
    setMenuOpen(false)
    try {
      const token = await authService.getMediaToken('video', video.id)
      const baseStreamUrl = videoService.getStreamUrl(video.id)
      const url = `${baseStreamUrl}?media_token=${encodeURIComponent(token)}`
      const a = document.createElement('a')
      a.href = url
      a.download = video.original_filename
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
    } catch {
      window.open(videoService.getStreamUrl(video.id), '_blank')
    }
  }

  return (
    <div className="group relative flex flex-col rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] hover:border-[var(--color-border-accent)] hover:shadow-[0_4px_24px_rgba(0,0,0,0.5)] transition-all duration-200 overflow-hidden">
      {/* 16:9 Thumbnail Screen */}
      <div
        className="relative aspect-video w-full bg-[#05080c] overflow-hidden cursor-pointer"
        onClick={() => onPlay(video)}
      >
        {thumbnailUrl && !thumbError ? (
          <img
            src={thumbnailUrl}
            alt={video.original_filename}
            onError={() => setThumbError(true)}
            className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
            loading="lazy"
          />
        ) : (
          <div className="w-full h-full flex flex-col items-center justify-center text-[var(--color-text-muted)] gap-2 bg-[var(--color-surface-2)]/60">
            <FileVideo className="w-8 h-8 opacity-40" />
            <span className="text-[10px] font-mono uppercase tracking-wider opacity-60">
              No Preview
            </span>
          </div>
        )}

        {/* Tactical Dark Gradient Overlay */}
        <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-black/10 to-transparent opacity-80 group-hover:opacity-60 transition-opacity" />

        {/* Hover Play Button Overlay */}
        <div className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity duration-200 bg-black/40 backdrop-blur-[2px]">
          <div className="w-12 h-12 rounded-full bg-[var(--color-accent)] text-[#04080e] flex items-center justify-center shadow-[0_0_20px_rgba(0,229,255,0.4)] transform scale-90 group-hover:scale-100 transition-transform">
            <Play className="w-5 h-5 fill-current ml-0.5" />
          </div>
        </div>

        {/* Live Processing Progress Bar */}
        {video.status === 'processing' && (
          <div className="absolute top-0 left-0 right-0 h-1 bg-black/80 z-20 overflow-hidden">
            <div
              className="h-full bg-[var(--color-accent)] transition-all duration-300 shadow-[0_0_8px_rgba(0,229,255,0.8)]"
              style={{ width: `${Math.max(5, video.processing_progress)}%` }}
            />
          </div>
        )}

        {/* Top Badges: Status */}
        <div className="absolute top-2.5 left-2.5 flex items-center gap-1.5 z-10">
          <Badge variant={video.status} dot>
            {video.status === 'processing'
              ? `Processing ${Math.round(video.processing_progress)}%`
              : video.status}
          </Badge>
        </div>

        {/* Bottom Left Badge: Resolution */}
        <div className="absolute bottom-2 left-2 z-10">
          <Badge variant="telemetry">
            {getResolutionLabel(video.width, video.height)}
          </Badge>
        </div>

        {/* Bottom Right Badge: Duration */}
        <div className="absolute bottom-2 right-2 z-10">
          <div className="px-2 py-0.5 rounded bg-black/80 backdrop-blur-sm border border-white/10 font-mono text-[11px] font-bold text-white shadow-sm">
            {formatDuration(video.duration)}
          </div>
        </div>
      </div>

      {/* Card Information */}
      <div className="p-3.5 flex flex-col justify-between flex-1 gap-2.5">
        <div className="space-y-1">
          <div className="flex items-start justify-between gap-2">
            <h4
              onClick={() => onPlay(video)}
              className="text-xs font-mono font-bold text-[var(--color-text-primary)] hover:text-[var(--color-accent)] transition-colors line-clamp-1 cursor-pointer"
              title={video.original_filename}
            >
              {video.original_filename}
            </h4>

            {/* Actions Menu */}
            <div className="relative">
              <button
                onClick={(e) => {
                  e.stopPropagation()
                  setMenuOpen(!menuOpen)
                }}
                className="p-1 rounded text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)] hover:bg-[var(--color-surface-2)] cursor-pointer"
                aria-label="Actions"
              >
                <MoreVertical className="w-3.5 h-3.5" />
              </button>

              {menuOpen && (
                <>
                  <div
                    className="fixed inset-0 z-30"
                    onClick={() => setMenuOpen(false)}
                  />
                  <div className="absolute right-0 top-full mt-1 w-44 rounded-lg bg-[var(--color-surface-2)] border border-[var(--color-border-2)] shadow-xl z-40 py-1 text-xs font-mono">
                    <button
                      onClick={() => {
                        setMenuOpen(false)
                        onPlay(video)
                      }}
                      className="w-full flex items-center gap-2 px-3 py-1.5 text-left text-[var(--color-text-primary)] hover:bg-[var(--color-surface-3)] cursor-pointer"
                    >
                      <Maximize2 className="w-3.5 h-3.5 text-[var(--color-accent)]" />
                      <span>Inspect & Play</span>
                    </button>
                    {(video.status === 'failed' || video.status === 'uploaded') && onProcess && (
                      <button
                        onClick={() => {
                          setMenuOpen(false)
                          onProcess(video)
                        }}
                        className="w-full flex items-center gap-2 px-3 py-1.5 text-left text-[var(--color-accent)] hover:bg-[var(--color-surface-3)] cursor-pointer"
                      >
                        <RotateCw className="w-3.5 h-3.5 text-[var(--color-accent)]" />
                        <span>{video.status === 'failed' ? 'Retry Processing' : 'Start Processing'}</span>
                      </button>
                    )}
                    <button
                      onClick={handleDownload}
                      className="w-full flex items-center gap-2 px-3 py-1.5 text-left text-[var(--color-text-primary)] hover:bg-[var(--color-surface-3)] cursor-pointer"
                    >
                      <Download className="w-3.5 h-3.5 text-[var(--color-text-muted)]" />
                      <span>Download</span>
                    </button>
                    <div className="my-1 border-t border-[var(--color-border)]" />
                    <button
                      onClick={() => {
                        setMenuOpen(false)
                        onDelete(video)
                      }}
                      className="w-full flex items-center gap-2 px-3 py-1.5 text-left text-rose-400 hover:bg-rose-950/30 cursor-pointer"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                      <span>Delete Video</span>
                    </button>
                  </div>
                </>
              )}
            </div>
          </div>

          <p className="text-[11px] font-mono text-[var(--color-text-muted)] flex items-center gap-2">
            <span>{formatBytes(video.file_size)}</span>
            <span>•</span>
            <span>{video.fps ? `${video.fps} fps` : 'N/A'}</span>
          </p>

          {/* Target Tracking Summary Badge */}
          {video.video_metadata?.tracks_count !== undefined && video.video_metadata.tracks_count > 0 && (
            <div className="flex flex-wrap items-center gap-1.5 pt-0.5">
              <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-mono bg-cyan-950/60 text-[var(--color-accent)] border border-cyan-800/40 font-semibold">
                <Target className="w-2.5 h-2.5" />
                {video.video_metadata.tracks_count} {video.video_metadata.tracks_count === 1 ? 'Track' : 'Tracks'}
              </span>
              {video.video_metadata.detected_classes && video.video_metadata.detected_classes.slice(0, 2).map((cls) => (
                <span
                  key={cls}
                  className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-[var(--color-surface-2)] text-[var(--color-text-secondary)] border border-[var(--color-border)] capitalize"
                >
                  {cls}
                </span>
              ))}
            </div>
          )}
        </div>

        {/* Footer: Ingestion Time */}
        <div className="flex items-center justify-between pt-2 border-t border-[var(--color-border)] text-[10px] font-mono text-[var(--color-text-muted)]">
          <span>Ingested {formatRelativeTime(video.created_at)}</span>
          <span className="text-[var(--color-accent)] opacity-80 uppercase">
            {video.video_metadata?.format || 'MP4'}
          </span>
        </div>
      </div>
    </div>
  )
}
