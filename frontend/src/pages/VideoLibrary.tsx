/**
 * VideoLibraryPage – Enterprise surveillance video library and ingestion console.
 */
import { useState } from 'react'
import {
  UploadCloud,
  Search,
  Grid,
  List,
  Video as VideoIcon,
  Clock,
  HardDrive,
  RefreshCw,
  Film,
  Activity,
  X,
} from 'lucide-react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Card, CardContent } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { EmptyState, Skeleton } from '@/components/ui/Loading'
import { VideoCard } from '@/components/video/VideoCard'
import { VideoTableView } from '@/components/video/VideoTableView'
import { UploadModal } from '@/components/video/UploadModal'
import { VideoPlayerModal } from '@/components/video/VideoPlayerModal'
import { videoService } from '@/services/video'
import { formatBytes, formatDuration } from '@/lib/utils'
import type { Video } from '@/types'

type ViewMode = 'grid' | 'table'
type StatusFilter = 'all' | 'uploaded' | 'queued' | 'processing' | 'completed' | 'failed'

export function VideoLibraryPage() {
  const [searchQuery, setSearchQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all')
  const [viewMode, setViewMode] = useState<ViewMode>('grid')
  const [isUploadOpen, setIsUploadOpen] = useState(false)
  const [selectedVideo, setSelectedVideo] = useState<Video | null>(null)

  const queryClient = useQueryClient()

  // 1. Fetch real summary statistics
  const { data: stats, isLoading: statsLoading } = useQuery({
    queryKey: ['video-stats'],
    queryFn: videoService.getVideoStats,
    staleTime: 10_000,
  })

  // 2. Fetch video list with search & status filters + live polling when active
  const {
    data: videos = [],
    isLoading: videosLoading,
    isFetching,
    refetch,
  } = useQuery({
    queryKey: ['videos', { search: searchQuery, status: statusFilter }],
    queryFn: () =>
      videoService.listVideos({
        search: searchQuery || undefined,
        status: statusFilter !== 'all' ? statusFilter : undefined,
      }),
    refetchInterval: (query) => {
      const data = query.state.data as Video[] | undefined
      const hasActive = data?.some(
        (v) => v.status === 'processing' || v.status === 'queued'
      )
      return hasActive ? 2000 : false
    },
  })

  const handleRefresh = () => {
    queryClient.invalidateQueries({ queryKey: ['videos'] })
    queryClient.invalidateQueries({ queryKey: ['video-stats'] })
  }

  const handleProcess = async (video: Video) => {
    try {
      await videoService.processVideo(video.id)
      handleRefresh()
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to enqueue processing')
    }
  }

  const handleDelete = async (video: Video) => {
    const confirmed = window.confirm(
      `Delete footage '${video.original_filename}' and its extracted artifacts?`,
    )
    if (!confirmed) return

    try {
      await videoService.deleteVideo(video.id)
      handleRefresh()
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to delete video')
    }
  }

  // Keep selected video synchronized with active polling updates
  const activeSelectedVideo = selectedVideo
    ? videos.find((v) => v.id === selectedVideo.id) || selectedVideo
    : null

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-xl font-bold font-mono tracking-tight text-[var(--color-text-primary)] uppercase">
              Surveillance Footage Repository
            </h2>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[var(--color-surface-2)] text-[var(--color-accent)] border border-[var(--color-border-accent)]">
              {stats?.total_videos || 0} ASSETS
            </span>
          </div>
          <p className="text-xs text-[var(--color-text-secondary)] mt-1 max-w-2xl">
            Ingest, catalog, and inspect CCTV video streams. Video metadata is automatically
            extracted and prepared for object tracking and semantic AI search.
          </p>
        </div>

        {/* Primary Action Button */}
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={handleRefresh}
            title="Refresh Library"
            className="text-[var(--color-text-muted)] hover:text-white"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isFetching ? 'animate-spin' : ''}`} />
          </Button>
          <Button
            variant="primary"
            size="md"
            onClick={() => setIsUploadOpen(true)}
            className="shadow-[0_0_15px_rgba(0,229,255,0.25)]"
          >
            <UploadCloud className="w-4 h-4" />
            <span>Ingest Footage</span>
          </Button>
        </div>
      </div>

      {/* Summary Telemetry Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
        <MetricCard
          label="Total Footage"
          value={stats ? `${stats.total_videos} Feeds` : '0 Feeds'}
          sublabel="Repository Assets"
          icon={Film}
          loading={statsLoading}
        />
        <MetricCard
          label="Cumulative Duration"
          value={stats ? formatDuration(stats.total_duration_seconds) : '00:00'}
          sublabel={`${stats?.total_duration_seconds ? stats.total_duration_seconds.toFixed(0) : 0} seconds indexed`}
          icon={Clock}
          iconColor="text-[var(--color-accent)]"
          loading={statsLoading}
        />
        <MetricCard
          label="Ingested Volume"
          value={stats ? formatBytes(stats.total_size_bytes) : '0 B'}
          sublabel="Local SSD Storage"
          icon={HardDrive}
          iconColor="text-[var(--color-info)]"
          loading={statsLoading}
        />
        <MetricCard
          label="Active Pipeline"
          value={stats ? `${stats.processing_count} Active` : '0 Active'}
          sublabel={`${stats?.completed_count || 0} ready for investigation`}
          icon={Activity}
          iconColor={stats && stats.processing_count > 0 ? 'text-amber-400' : 'text-emerald-400'}
          loading={statsLoading}
        />
      </div>

      {/* Control Bar: Search, Filters & View Toggle */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 p-2.5 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] shadow-sm">
        {/* Search Input */}
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-[var(--color-text-muted)]" />
          <input
            type="text"
            placeholder="Search footage by filename..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full h-8 pl-8 pr-8 rounded-lg bg-[var(--color-surface-2)] border border-[var(--color-border)] text-xs text-[var(--color-text-primary)] placeholder-[var(--color-text-muted)] focus:outline-none focus:border-[var(--color-accent)] font-mono"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery('')}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-[var(--color-text-muted)] hover:text-white"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>

        {/* Status Filters & View Toggle */}
        <div className="flex items-center justify-between sm:justify-end gap-3">
          {/* Status Filter Tabs */}
          <div className="flex items-center p-0.5 rounded-lg bg-[var(--color-surface-2)] border border-[var(--color-border)] text-xs font-mono overflow-x-auto">
            {(['all', 'uploaded', 'processing', 'completed', 'failed'] as StatusFilter[]).map((st) => (
              <button
                key={st}
                onClick={() => setStatusFilter(st)}
                className={`px-2.5 py-1 rounded-md text-[11px] uppercase tracking-wider font-semibold transition-all cursor-pointer ${
                  statusFilter === st
                    ? 'bg-[var(--color-accent)] text-[#04080e] shadow-sm'
                    : 'text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)]'
                }`}
              >
                {st}
              </button>
            ))}
          </div>

          {/* View Mode Toggle */}
          <div className="flex items-center p-0.5 rounded-lg bg-[var(--color-surface-2)] border border-[var(--color-border)]">
            <button
              onClick={() => setViewMode('grid')}
              className={`p-1.5 rounded transition-colors cursor-pointer ${
                viewMode === 'grid'
                  ? 'bg-[var(--color-surface-3)] text-[var(--color-accent)] shadow-sm'
                  : 'text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)]'
              }`}
              title="Grid View"
              aria-label="Grid view"
            >
              <Grid className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={() => setViewMode('table')}
              className={`p-1.5 rounded transition-colors cursor-pointer ${
                viewMode === 'table'
                  ? 'bg-[var(--color-surface-3)] text-[var(--color-accent)] shadow-sm'
                  : 'text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)]'
              }`}
              title="Table View"
              aria-label="Table view"
            >
              <List className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>

      {/* Content Area: Grid / Table / Loading / Empty */}
      {videosLoading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <div
              key={i}
              className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] overflow-hidden space-y-3 p-3"
            >
              <Skeleton className="aspect-video w-full rounded-lg" />
              <div className="space-y-1.5">
                <Skeleton className="h-4 w-3/4" />
                <Skeleton className="h-3 w-1/2" />
              </div>
            </div>
          ))}
        </div>
      ) : videos.length === 0 ? (
        searchQuery || statusFilter !== 'all' ? (
          <EmptyState
            icon={<Search className="w-8 h-8" />}
            title="No Matching Footage Found"
            description={`No surveillance video matches query "${searchQuery}" with status "${statusFilter}".`}
            action={
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  setSearchQuery('')
                  setStatusFilter('all')
                }}
              >
                Clear Filters
              </Button>
            }
          />
        ) : (
          <EmptyState
            icon={<VideoIcon className="w-8 h-8" />}
            title="Footage Repository is Empty"
            description="No surveillance footage has been uploaded to the system yet. Ingest your first video file to begin automated computer vision indexing."
            action={
              <Button
                variant="primary"
                size="md"
                onClick={() => setIsUploadOpen(true)}
              >
                <UploadCloud className="w-4 h-4" />
                <span>Upload First Video</span>
              </Button>
            }
          />
        )
      ) : viewMode === 'grid' ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {videos.map((video) => (
            <VideoCard
              key={video.id}
              video={video}
              onPlay={(v) => setSelectedVideo(v)}
              onDelete={handleDelete}
              onProcess={handleProcess}
            />
          ))}
        </div>
      ) : (
        <VideoTableView
          videos={videos}
          onPlay={(v) => setSelectedVideo(v)}
          onDelete={handleDelete}
          onProcess={handleProcess}
        />
      )}

      {/* Upload Modal */}
      <UploadModal
        isOpen={isUploadOpen}
        onClose={() => setIsUploadOpen(false)}
        onSuccess={handleRefresh}
      />

      {/* Video Player Modal */}
      <VideoPlayerModal
        video={activeSelectedVideo}
        isOpen={activeSelectedVideo !== null}
        onClose={() => setSelectedVideo(null)}
        onDeleteSuccess={handleRefresh}
        onProcess={handleProcess}
      />
    </div>
  )
}

function MetricCard({
  label,
  value,
  sublabel,
  icon: Icon,
  iconColor = 'text-[var(--color-accent)]',
  loading,
}: {
  label: string
  value: string
  sublabel: string
  icon: React.ElementType
  iconColor?: string
  loading?: boolean
}) {
  return (
    <Card className="border-[var(--color-border)] bg-[var(--color-surface)]">
      <CardContent className="p-4 sm:p-5">
        <div className="flex items-start justify-between">
          <div className="space-y-1">
            <p className="text-[10px] font-mono uppercase tracking-wider text-[var(--color-text-muted)] font-semibold">
              {label}
            </p>
            {loading ? (
              <Skeleton className="h-7 w-24" />
            ) : (
              <p className="text-xl sm:text-2xl font-bold font-mono text-[var(--color-text-primary)]">
                {value}
              </p>
            )}
            <p className="text-[11px] font-mono text-[var(--color-text-secondary)]">
              {sublabel}
            </p>
          </div>
          <div className="p-2.5 rounded-lg bg-[var(--color-surface-2)] border border-[var(--color-border)] shrink-0">
            <Icon className={`w-4 h-4 ${iconColor}`} />
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
