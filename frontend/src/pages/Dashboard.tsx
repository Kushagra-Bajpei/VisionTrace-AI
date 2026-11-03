/**
 * Dashboard page – Operational overview, live feed telemetry, and surveillance metrics.
 */
import {
  Film,
  Clock,
  AlertCircle,
  FolderSearch,
  Activity,
  ArrowUpRight,
  Server,
  UploadCloud,
  Play,
  FileVideo,
} from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Skeleton } from '@/components/ui/Loading'
import { useApiHealth, useDetailedHealth } from '@/hooks/useApiHealth'
import { videoService } from '@/services/video'
import { formatBytes, formatDuration, formatRelativeTime, getResolutionLabel } from '@/lib/utils'
import { Link } from 'react-router-dom'

interface StatCardProps {
  title: string
  value: string | number
  delta?: string
  icon: React.ElementType
  iconColor?: string
  loading?: boolean
}

function StatCard({
  title,
  value,
  delta,
  icon: Icon,
  iconColor = 'text-[var(--color-accent)]',
  loading,
}: StatCardProps) {
  return (
    <Card className="border-[var(--color-border)] bg-[var(--color-surface)]">
      <CardContent className="pt-5">
        <div className="flex items-start justify-between">
          <div className="space-y-1">
            <p className="text-[10px] font-mono font-semibold text-[var(--color-text-muted)] uppercase tracking-wider">
              {title}
            </p>
            {loading ? (
              <Skeleton className="h-8 w-24" />
            ) : (
              <p className="text-2xl font-bold font-mono text-[var(--color-text-primary)]">
                {value}
              </p>
            )}
            {delta && !loading && (
              <p className="text-xs font-mono text-[var(--color-text-secondary)]">{delta}</p>
            )}
          </div>
          <div className="p-2.5 rounded-lg bg-[var(--color-surface-2)] border border-[var(--color-border)]">
            <Icon className={`w-4 h-4 ${iconColor}`} />
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

export function DashboardPage() {
  const { health, isConnected, isLoading: healthLoading } = useApiHealth()
  const { detailedHealth } = useDetailedHealth()

  // Real summary metrics from Video API
  const { data: stats, isLoading: statsLoading } = useQuery({
    queryKey: ['video-stats'],
    queryFn: videoService.getVideoStats,
    staleTime: 15_000,
  })

  // Real recent uploads from Video API
  const { data: recentVideos = [], isLoading: videosLoading } = useQuery({
    queryKey: ['recent-videos'],
    queryFn: () => videoService.listVideos({ limit: 4 }),
    staleTime: 15_000,
  })

  const dbStatus = detailedHealth?.subsystems?.database?.status
  const isDbOk = dbStatus === 'ok'

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-8">
      {/* Page header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-xl font-bold font-mono tracking-tight text-[var(--color-text-primary)] uppercase">
              Operational Command Console
            </h2>
            <Badge variant="accent">LIVE</Badge>
          </div>
          <p className="text-xs text-[var(--color-text-secondary)] mt-0.5">
            Real-time surveillance feeds, automated object detection status, and active incident workflows.
          </p>
        </div>
        <Button variant="primary" size="sm" asChild>
          <Link to="/videos" className="flex items-center gap-2">
            <UploadCloud className="w-4 h-4" />
            <span>Ingest Footage</span>
          </Link>
        </Button>
      </div>

      {/* Stat cards driven by real API telemetry */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Ingested Feeds"
          value={stats ? `${stats.total_videos} Feeds` : '0 Feeds'}
          delta={stats && stats.total_videos > 0 ? `${formatBytes(stats.total_size_bytes)} indexed` : 'Awaiting uploads'}
          icon={Film}
          loading={statsLoading}
        />
        <StatCard
          title="Processed Footage"
          value={stats ? formatDuration(stats.total_duration_seconds) : '00:00'}
          delta={stats ? `${stats.completed_count} ready for search` : 'Queue idle'}
          icon={Clock}
          iconColor="text-[var(--color-info)]"
          loading={statsLoading}
        />
        <StatCard
          title="Detected Events"
          value="0"
          delta="CV Pipeline queued"
          icon={AlertCircle}
          iconColor="text-[var(--color-warning)]"
        />
        <StatCard
          title="Active Investigations"
          value="0"
          delta="No open cases"
          icon={FolderSearch}
          iconColor="text-[var(--color-success)]"
        />
      </div>

      {/* Two-column section */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Recent Ingested Footage */}
        <Card className="lg:col-span-2 border-[var(--color-border)] bg-[var(--color-surface)]">
          <CardHeader className="flex flex-row items-center justify-between pb-3">
            <div>
              <CardTitle>Recent Surveillance Feeds</CardTitle>
              <CardDescription>
                Latest CCTV video streams ingested into storage.
              </CardDescription>
            </div>
            <Button variant="ghost" size="xs" asChild>
              <Link to="/videos" className="flex items-center gap-1 text-[var(--color-accent)]">
                <span>View All</span>
                <ArrowUpRight className="w-3.5 h-3.5" />
              </Link>
            </Button>
          </CardHeader>
          <CardContent>
            {videosLoading ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <Skeleton className="h-28 w-full rounded-lg" />
                <Skeleton className="h-28 w-full rounded-lg" />
              </div>
            ) : recentVideos.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-10 gap-3 text-center">
                <div className="p-3 rounded-full bg-[var(--color-surface-2)] text-[var(--color-text-muted)]">
                  <Film className="w-6 h-6 opacity-40" />
                </div>
                <div className="space-y-1">
                  <p className="text-xs font-mono font-semibold text-[var(--color-text-primary)]">
                    No footage ingested yet
                  </p>
                  <p className="text-[11px] text-[var(--color-text-secondary)] max-w-xs">
                    Upload an MP4, MOV, or AVI surveillance stream to populate the intelligence repository.
                  </p>
                </div>
                <Button variant="outline" size="sm" asChild className="mt-1">
                  <Link to="/videos">Open Video Ingestion</Link>
                </Button>
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {recentVideos.map((v) => (
                  <Link
                    key={v.id}
                    to="/videos"
                    className="flex gap-3 p-2.5 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-2)] hover:border-[var(--color-border-accent)] transition-all group"
                  >
                    <div className="relative w-24 aspect-video rounded bg-black shrink-0 overflow-hidden">
                      {v.thumbnail_path ? (
                        <img
                          src={videoService.getThumbnailUrl(v.id)}
                          alt=""
                          className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-200"
                        />
                      ) : (
                        <div className="w-full h-full flex items-center justify-center text-[var(--color-text-muted)]">
                          <FileVideo className="w-5 h-5 opacity-40" />
                        </div>
                      )}
                      <div className="absolute inset-0 bg-black/30 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
                        <Play className="w-4 h-4 text-[var(--color-accent)] fill-current" />
                      </div>
                    </div>
                    <div className="flex flex-col justify-between min-w-0 flex-1">
                      <div>
                        <p className="text-xs font-mono font-bold text-[var(--color-text-primary)] truncate group-hover:text-[var(--color-accent)] transition-colors">
                          {v.original_filename}
                        </p>
                        <p className="text-[10px] font-mono text-[var(--color-text-muted)] mt-0.5">
                          {formatDuration(v.duration)} • {getResolutionLabel(v.width, v.height)}
                        </p>
                      </div>
                      <div className="flex items-center justify-between mt-1 text-[10px] font-mono text-[var(--color-text-secondary)]">
                        <span>{formatRelativeTime(v.created_at)}</span>
                        <Badge variant={v.status} dot>
                          {v.status}
                        </Badge>
                      </div>
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* System Telemetry Card */}
        <Card className="border-[var(--color-border)] bg-[var(--color-surface)]">
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle>System Telemetry</CardTitle>
              <Badge variant={isConnected ? 'completed' : 'failed'} dot>
                {isConnected ? 'ONLINE' : 'OFFLINE'}
              </Badge>
            </div>
            <CardDescription>Pipeline infrastructure health monitoring.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {healthLoading ? (
              <div className="space-y-2">
                <Skeleton className="h-8 w-full" />
                <Skeleton className="h-8 w-full" />
                <Skeleton className="h-8 w-full" />
              </div>
            ) : (
              <>
                <StatusRow
                  label="FastAPI Gateway"
                  status={isConnected ? 'ok' : 'error'}
                  detail={health ? `v${health.version}` : '—'}
                />
                <StatusRow
                  label="PostgreSQL / pgvector"
                  status={isDbOk ? 'ok' : 'pending'}
                  detail={isDbOk ? 'Connected' : 'Schema Active'}
                />
                <StatusRow
                  label="Local Storage Engine"
                  status="ok"
                  detail={stats ? formatBytes(stats.total_size_bytes) : 'Active'}
                />
                <StatusRow
                  label="Task Queue (Redis)"
                  status="pending"
                  detail="Phase 4"
                />
                <StatusRow
                  label="AI Detection Pipeline"
                  status="pending"
                  detail="Phase 5"
                />
                {health && (
                  <div className="pt-2 border-t border-[var(--color-border)] text-xs font-mono text-[var(--color-text-muted)] space-y-1">
                    <div className="flex items-center justify-between">
                      <span className="flex items-center gap-1.5">
                        <Activity className="w-3 h-3 text-[var(--color-accent)]" />
                        Uptime:
                      </span>
                      <span>{Math.floor(health.uptime_seconds)}s</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="flex items-center gap-1.5">
                        <Server className="w-3 h-3 text-[var(--color-accent)]" />
                        Environment:
                      </span>
                      <span className="uppercase">{health.environment}</span>
                    </div>
                  </div>
                )}
              </>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Phase progress banner */}
      <Card className="border-[var(--color-border-accent)] bg-[var(--color-surface-2)] shadow-sm">
        <CardContent className="py-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <div className="w-2.5 h-2.5 rounded-full bg-[var(--color-accent)] animate-pulse shadow-[0_0_8px_rgba(0,229,255,0.7)] shrink-0" />
              <div>
                <p className="text-xs font-mono font-bold text-[var(--color-accent)] uppercase tracking-wide">
                  Phase 3 Operational — Ingestion & Video Library Complete
                </p>
                <p className="text-xs text-[var(--color-text-secondary)] mt-0.5">
                  Surveillance footage streaming, chunked uploads, metadata extraction, and thumbnail generation are operational. Next: Phase 4 — Redis queue and Celery worker async processing.
                </p>
              </div>
            </div>
            <Badge variant="accent">PHASE 3 / 11</Badge>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

function StatusRow({
  label,
  status,
  detail,
}: {
  label: string
  status: 'ok' | 'error' | 'pending'
  detail: string
}) {
  const colors = {
    ok: 'bg-[var(--color-success)] shadow-[0_0_6px_rgba(16,185,129,0.5)]',
    error: 'bg-[var(--color-danger)] animate-pulse',
    pending: 'bg-[var(--color-text-muted)]',
  }
  const textColors = {
    ok: 'text-[var(--color-success)]',
    error: 'text-[var(--color-danger)]',
    pending: 'text-[var(--color-text-muted)]',
  }

  return (
    <div className="flex items-center justify-between py-2 border-b border-[var(--color-border)] last:border-0 font-mono text-xs">
      <div className="flex items-center gap-2">
        <div className={`w-1.5 h-1.5 rounded-full ${colors[status]}`} />
        <span className="text-[var(--color-text-secondary)]">{label}</span>
      </div>
      <span className={`text-[11px] font-bold ${textColors[status]}`}>
        {detail}
      </span>
    </div>
  )
}
