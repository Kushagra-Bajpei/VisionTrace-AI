/**
 * Investigations Page (Phase 7).
 * Enterprise surveillance case management and evidentiary dossier library.
 */
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  FolderSearch,
  Plus,
  Search,
  ShieldAlert,
  Clock,
  Tag,
  Layers,
  ChevronRight,
  Filter,
  CheckCircle2,
  AlertTriangle,
  RotateCw,
} from 'lucide-react'
import { Card, CardContent } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Modal } from '@/components/ui/Modal'
import { Spinner } from '@/components/ui/Loading'
import { investigationService } from '@/services/investigation'
import { formatDateTime } from '@/lib/utils'
import type { CasePriority, CaseStatus, InvestigationCase } from '@/types'

const STATUS_TABS: Array<{ label: string; value: string }> = [
  { label: 'All Cases', value: 'all' },
  { label: 'Open', value: 'open' },
  { label: 'In Progress', value: 'in_progress' },
  { label: 'Under Review', value: 'under_review' },
  { label: 'Closed', value: 'closed' },
]

export function InvestigationsPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const [activeStatus, setActiveStatus] = useState<string>('all')
  const [priorityFilter, setPriorityFilter] = useState<string>('all')
  const [searchQuery, setSearchQuery] = useState<string>('')
  const [isCreateOpen, setIsCreateOpen] = useState<boolean>(false)

  // Form state
  const [newTitle, setNewTitle] = useState('')
  const [newDesc, setNewDesc] = useState('')
  const [newPriority, setNewPriority] = useState<CasePriority>('medium')
  const [newTagsStr, setNewTagsStr] = useState('')

  const {
    data: cases = [],
    isLoading,
    isRefetching,
    refetch,
  } = useQuery({
    queryKey: ['cases', activeStatus, priorityFilter, searchQuery],
    queryFn: () =>
      investigationService.listCases({
        status: activeStatus,
        priority: priorityFilter,
        search: searchQuery.trim() || undefined,
      }),
  })

  const createMutation = useMutation({
    mutationFn: investigationService.createCase,
    onSuccess: (newCase) => {
      queryClient.invalidateQueries({ queryKey: ['cases'] })
      setIsCreateOpen(false)
      setNewTitle('')
      setNewDesc('')
      setNewTagsStr('')
      navigate(`/investigations/${newCase.id}`)
    },
  })

  const handleCreateSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!newTitle.trim()) return

    const tags = newTagsStr
      .split(',')
      .map((t) => t.trim().toLowerCase())
      .filter(Boolean)

    createMutation.mutate({
      title: newTitle.trim(),
      description: newDesc.trim() || undefined,
      priority: newPriority,
      status: 'open',
      tags,
    })
  }

  const getPriorityBadge = (p: CasePriority) => {
    switch (p) {
      case 'critical':
        return <Badge variant="danger" className="uppercase font-mono text-[10px]">Critical</Badge>
      case 'high':
        return <Badge variant="warning" className="uppercase font-mono text-[10px]">High</Badge>
      case 'medium':
        return <Badge variant="accent" className="uppercase font-mono text-[10px]">Medium</Badge>
      default:
        return <Badge variant="default" className="uppercase font-mono text-[10px]">Low</Badge>
    }
  }

  const getStatusBadge = (s: CaseStatus) => {
    switch (s) {
      case 'open':
        return <Badge variant="accent" className="uppercase font-mono text-[10px]">Open</Badge>
      case 'in_progress':
        return <Badge variant="warning" className="uppercase font-mono text-[10px]">In Progress</Badge>
      case 'under_review':
        return <Badge variant="queued" className="uppercase font-mono text-[10px]">Under Review</Badge>
      case 'closed':
        return <Badge variant="success" className="uppercase font-mono text-[10px]">Closed</Badge>
      default:
        return <Badge variant="default" className="uppercase font-mono text-[10px]">{s}</Badge>
    }
  }

  return (
    <div className="space-y-6">
      {/* ── Top Bar / Header ── */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold tracking-tight text-[var(--color-text-primary)]">
              Investigation Cases
            </h1>
            <span className="font-mono text-xs px-2 py-0.5 rounded bg-[var(--color-surface-2)] text-[var(--color-accent)] border border-[var(--color-border)]">
              EVIDENTIARY DOSSIERS
            </span>
          </div>
          <p className="text-xs text-[var(--color-text-muted)] mt-1">
            Structured forensic case management, evidentiary timelines, and audit-grade incident reporting.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => refetch()}
            disabled={isLoading || isRefetching}
            className="text-[var(--color-text-secondary)]"
          >
            <RotateCw className={`w-3.5 h-3.5 mr-1.5 ${isRefetching ? 'animate-spin' : ''}`} />
            Refresh
          </Button>

          <Button
            variant="primary"
            size="sm"
            onClick={() => setIsCreateOpen(true)}
            className="bg-[var(--color-accent)] text-black hover:bg-[var(--color-accent-hover)] font-semibold shadow-[0_0_15px_rgba(0,229,255,0.2)]"
          >
            <Plus className="w-4 h-4 mr-1.5" />
            New Investigation
          </Button>
        </div>
      </div>

      {/* ── Filter Bar ── */}
      <Card className="border-[var(--color-border)] bg-[var(--color-surface-1)]">
        <CardContent className="p-3">
          <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3">
            {/* Status Tabs */}
            <div className="flex items-center gap-1 overflow-x-auto pb-1 lg:pb-0">
              {STATUS_TABS.map((tab) => (
                <button
                  key={tab.value}
                  onClick={() => setActiveStatus(tab.value)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors whitespace-nowrap ${
                    activeStatus === tab.value
                      ? 'bg-[var(--color-surface-2)] text-[var(--color-accent)] border border-[var(--color-border-accent)]'
                      : 'text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] hover:bg-[var(--color-surface-2)]'
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            {/* Search and Priority filters */}
            <div className="flex items-center gap-2">
              <div className="relative flex-1 sm:w-64">
                <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-[var(--color-text-muted)]" />
                <input
                  type="text"
                  placeholder="Filter cases by title..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-lg pl-8 pr-3 py-1.5 text-xs text-[var(--color-text-primary)] placeholder-[var(--color-text-muted)] focus:outline-none focus:border-[var(--color-accent)]"
                />
              </div>

              <select
                value={priorityFilter}
                onChange={(e) => setPriorityFilter(e.target.value)}
                className="bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-lg px-2.5 py-1.5 text-xs text-[var(--color-text-secondary)] focus:outline-none focus:border-[var(--color-accent)]"
              >
                <option value="all">All Priorities</option>
                <option value="critical">Critical</option>
                <option value="high">High</option>
                <option value="medium">Medium</option>
                <option value="low">Low</option>
              </select>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* ── Case Grid / List ── */}
      {isLoading ? (
        <div className="flex flex-col items-center justify-center py-20 text-center gap-3">
          <Spinner className="w-7 h-7 text-[var(--color-accent)]" />
          <p className="text-xs text-[var(--color-text-muted)]">Loading case dossiers...</p>
        </div>
      ) : cases.length === 0 ? (
        <Card className="border-[var(--color-border)] bg-[var(--color-surface-1)]">
          <CardContent className="py-16 text-center">
            <div className="w-12 h-12 rounded-xl bg-[var(--color-surface-2)] border border-[var(--color-border)] flex items-center justify-center mx-auto mb-3 text-[var(--color-text-muted)]">
              <FolderSearch className="w-6 h-6" />
            </div>
            <h3 className="text-sm font-semibold text-[var(--color-text-primary)]">
              No investigation cases found
            </h3>
            <p className="text-xs text-[var(--color-text-muted)] max-w-sm mx-auto mt-1 mb-4">
              {searchQuery || activeStatus !== 'all' || priorityFilter !== 'all'
                ? 'Try adjusting your filters or search keywords.'
                : 'Create your first investigation case to start grouping CCTV evidence items.'}
            </p>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setIsCreateOpen(true)}
              className="text-xs border-[var(--color-border)]"
            >
              <Plus className="w-3.5 h-3.5 mr-1.5" />
              Open New Case
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {cases.map((caseItem: InvestigationCase) => (
            <Card
              key={caseItem.id}
              onClick={() => navigate(`/investigations/${caseItem.id}`)}
              className="group cursor-pointer border-[var(--color-border)] bg-[var(--color-surface-1)] hover:border-[var(--color-accent)] transition-all hover:shadow-[0_0_20px_rgba(0,229,255,0.06)]"
            >
              <CardContent className="p-4 space-y-3">
                {/* Header: Status and Priority */}
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-1.5">
                    {getStatusBadge(caseItem.status)}
                    {getPriorityBadge(caseItem.priority)}
                  </div>
                  <div className="flex items-center text-[10px] font-mono text-[var(--color-text-muted)]">
                    <Clock className="w-3 h-3 mr-1" />
                    {formatDateTime(caseItem.updated_at)}
                  </div>
                </div>

                {/* Title and Description */}
                <div>
                  <h3 className="text-sm font-semibold text-[var(--color-text-primary)] group-hover:text-[var(--color-accent)] transition-colors line-clamp-1">
                    {caseItem.title}
                  </h3>
                  <p className="text-xs text-[var(--color-text-secondary)] line-clamp-2 mt-1">
                    {caseItem.description || 'No case overview documented yet.'}
                  </p>
                </div>

                {/* Tags */}
                {caseItem.tags && caseItem.tags.length > 0 && (
                  <div className="flex flex-wrap gap-1">
                    {caseItem.tags.slice(0, 3).map((tag) => (
                      <span
                        key={tag}
                        className="text-[10px] px-1.5 py-0.5 rounded bg-[var(--color-surface-2)] text-[var(--color-text-muted)] border border-[var(--color-border)] font-mono"
                      >
                        #{tag}
                      </span>
                    ))}
                    {caseItem.tags.length > 3 && (
                      <span className="text-[10px] px-1 py-0.5 text-[var(--color-text-muted)]">
                        +{caseItem.tags.length - 3}
                      </span>
                    )}
                  </div>
                )}

                {/* Footer info */}
                <div className="pt-2 border-t border-[var(--color-border)] flex items-center justify-between text-xs">
                  <div className="flex items-center gap-1.5 text-[var(--color-text-secondary)] font-mono text-[11px]">
                    <Layers className="w-3.5 h-3.5 text-[var(--color-accent)]" />
                    <span>{caseItem.evidence_count} evidence item{caseItem.evidence_count !== 1 ? 's' : ''}</span>
                  </div>

                  <span className="flex items-center text-[11px] font-medium text-[var(--color-accent)] group-hover:translate-x-0.5 transition-transform">
                    Enter Workspace
                    <ChevronRight className="w-3.5 h-3.5 ml-0.5" />
                  </span>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* ── Create Case Modal ── */}
      <Modal
        isOpen={isCreateOpen}
        onClose={() => setIsCreateOpen(false)}
        title="Create Investigation Case"
      >
        <form onSubmit={handleCreateSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-[var(--color-text-secondary)] mb-1">
              Case Title <span className="text-red-400">*</span>
            </label>
            <input
              type="text"
              required
              placeholder="e.g. Unauthorized Perimeter Approach #204"
              value={newTitle}
              onChange={(e) => setNewTitle(e.target.value)}
              className="w-full bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-lg px-3 py-2 text-xs text-[var(--color-text-primary)] placeholder-[var(--color-text-muted)] focus:outline-none focus:border-[var(--color-accent)]"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-[var(--color-text-secondary)] mb-1">
              Initial Briefing / Description
            </label>
            <textarea
              rows={3}
              placeholder="Provide context regarding the incident, target zone, or camera locations..."
              value={newDesc}
              onChange={(e) => setNewDesc(e.target.value)}
              className="w-full bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-lg px-3 py-2 text-xs text-[var(--color-text-primary)] placeholder-[var(--color-text-muted)] focus:outline-none focus:border-[var(--color-accent)] resize-none"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-[var(--color-text-secondary)] mb-1">
                Priority Level
              </label>
              <select
                value={newPriority}
                onChange={(e) => setNewPriority(e.target.value as CasePriority)}
                className="w-full bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-lg px-2.5 py-2 text-xs text-[var(--color-text-primary)] focus:outline-none focus:border-[var(--color-accent)]"
              >
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
                <option value="critical">Critical</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-medium text-[var(--color-text-secondary)] mb-1">
                Tags (comma separated)
              </label>
              <input
                type="text"
                placeholder="perimeter, night-shift, suspect"
                value={newTagsStr}
                onChange={(e) => setNewTagsStr(e.target.value)}
                className="w-full bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-lg px-3 py-2 text-xs text-[var(--color-text-primary)] placeholder-[var(--color-text-muted)] focus:outline-none focus:border-[var(--color-accent)]"
              />
            </div>
          </div>

          <div className="flex items-center justify-end gap-2 pt-3 border-t border-[var(--color-border)]">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => setIsCreateOpen(false)}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
              size="sm"
              disabled={createMutation.isPending || !newTitle.trim()}
              className="bg-[var(--color-accent)] text-black hover:bg-[var(--color-accent-hover)] font-semibold"
            >
              {createMutation.isPending ? (
                <>
                  <Spinner className="w-3.5 h-3.5 mr-1.5" />
                  Creating...
                </>
              ) : (
                'Create Dossier'
              )}
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  )
}
export default InvestigationsPage
