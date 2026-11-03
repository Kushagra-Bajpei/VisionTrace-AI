/**
 * VideoTableView – High-density tabular view for enterprise surveillance footage.
 */
import { Play, Download, Trash2, FileVideo, RotateCw } from 'lucide-react'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { videoService } from '@/services/video'
import { authService } from '@/services/auth'
import { formatBytes, formatDuration, formatDateTime, getResolutionLabel } from '@/lib/utils'
import type { Video } from '@/types'

interface VideoTableViewProps {
  videos: Video[]
  onPlay: (video: Video) => void
  onDelete: (video: Video) => void
  onProcess?: (video: Video) => void
}

export function VideoTableView({ videos, onPlay, onDelete, onProcess }: VideoTableViewProps) {
  const handleDownload = async (video: Video) => {
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
    <div className="w-full rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] overflow-hidden shadow-sm">
      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs font-mono">
          <thead className="bg-[var(--color-surface-2)]/60 border-b border-[var(--color-border)] text-[10px] uppercase tracking-wider text-[var(--color-text-muted)] select-none">
            <tr>
              <th className="py-3 px-4 w-28">Preview</th>
              <th className="py-3 px-4">Filename / Source</th>
              <th className="py-3 px-4">Status</th>
              <th className="py-3 px-4">Resolution</th>
              <th className="py-3 px-4">Duration</th>
              <th className="py-3 px-4">FPS</th>
              <th className="py-3 px-4">File Size</th>
              <th className="py-3 px-4">Ingested At</th>
              <th className="py-3 px-4 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--color-border)]">
            {videos.map((video) => {
              const thumbUrl = video.thumbnail_path
                ? videoService.getThumbnailUrl(video.id)
                : null

              return (
                <tr
                  key={video.id}
                  className="hover:bg-[var(--color-surface-2)]/50 transition-colors group"
                >
                  {/* Thumbnail */}
                  <td className="py-2.5 px-4">
                    <div
                      onClick={() => onPlay(video)}
                      className="relative w-20 aspect-video rounded-md bg-black border border-[var(--color-border)] overflow-hidden cursor-pointer group-hover:border-[var(--color-accent)] transition-colors"
                    >
                      {thumbUrl ? (
                        <img
                          src={thumbUrl}
                          alt=""
                          className="w-full h-full object-cover"
                          loading="lazy"
                        />
                      ) : (
                        <div className="w-full h-full flex items-center justify-center text-[var(--color-text-muted)]">
                          <FileVideo className="w-4 h-4 opacity-40" />
                        </div>
                      )}
                      <div className="absolute inset-0 bg-black/40 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
                        <Play className="w-4 h-4 text-[var(--color-accent)] fill-current" />
                      </div>
                    </div>
                  </td>

                  {/* Filename */}
                  <td className="py-2.5 px-4 font-semibold text-[var(--color-text-primary)] max-w-xs">
                    <div
                      onClick={() => onPlay(video)}
                      className="truncate hover:text-[var(--color-accent)] cursor-pointer"
                      title={video.original_filename}
                    >
                      {video.original_filename}
                    </div>
                    <div className="text-[10px] text-[var(--color-text-muted)] truncate">
                      {video.id}
                    </div>
                  </td>

                  {/* Status */}
                  <td className="py-2.5 px-4">
                    <div className="flex flex-col gap-1 w-28">
                      <Badge variant={video.status} dot>
                        {video.status === 'processing'
                          ? `${Math.round(video.processing_progress)}%`
                          : video.status}
                      </Badge>
                      {video.status === 'processing' && (
                        <div className="w-full h-1 bg-[var(--color-surface-3)] rounded-full overflow-hidden">
                          <div
                            className="h-full bg-[var(--color-accent)] transition-all duration-300"
                            style={{ width: `${Math.max(5, video.processing_progress)}%` }}
                          />
                        </div>
                      )}
                    </div>
                  </td>

                  {/* Resolution */}
                  <td className="py-2.5 px-4">
                    <span className="text-[var(--color-text-secondary)]">
                      {getResolutionLabel(video.width, video.height)}
                    </span>
                  </td>

                  {/* Duration */}
                  <td className="py-2.5 px-4 font-bold text-[var(--color-text-primary)]">
                    {formatDuration(video.duration)}
                  </td>

                  {/* FPS */}
                  <td className="py-2.5 px-4 text-[var(--color-text-secondary)]">
                    {video.fps ? `${video.fps} fps` : '—'}
                  </td>

                  {/* Size */}
                  <td className="py-2.5 px-4 text-[var(--color-text-secondary)]">
                    {formatBytes(video.file_size)}
                  </td>

                  {/* Date */}
                  <td className="py-2.5 px-4 text-[var(--color-text-muted)] text-[11px]">
                    {formatDateTime(video.created_at)}
                  </td>

                  {/* Actions */}
                  <td className="py-2.5 px-4 text-right">
                    <div className="flex items-center justify-end gap-1">
                      {(video.status === 'failed' || video.status === 'uploaded') && onProcess && (
                        <Button
                          variant="ghost"
                          size="icon-sm"
                          onClick={() => onProcess(video)}
                          title={video.status === 'failed' ? 'Retry Processing' : 'Start Processing'}
                          className="text-[var(--color-accent)] hover:bg-[var(--color-surface-3)]"
                        >
                          <RotateCw className="w-3.5 h-3.5" />
                        </Button>
                      )}
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        onClick={() => onPlay(video)}
                        title="Inspect & Play"
                        className="text-[var(--color-accent)] hover:bg-[var(--color-surface-3)]"
                      >
                        <Play className="w-3.5 h-3.5 fill-current" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        onClick={() => handleDownload(video)}
                        title="Download"
                      >
                        <Download className="w-3.5 h-3.5" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        onClick={() => onDelete(video)}
                        title="Delete"
                        className="text-rose-400 hover:bg-rose-950/40"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </Button>
                    </div>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
