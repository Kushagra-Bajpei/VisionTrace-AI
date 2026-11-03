/**
 * Placeholder pages for features implemented in later phases.
 * Each shows a clear "Coming in Phase X" message so the app shell is complete.
 */
import { Video, Search, FolderSearch, FileText, Settings2, Construction } from 'lucide-react'
import { Card, CardContent } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'

interface PlaceholderProps {
  icon: React.ElementType
  title: string
  description: string
  phase: string
  features: string[]
}

function Placeholder({ icon: Icon, title, description, phase, features }: PlaceholderProps) {
  return (
    <div className="max-w-2xl mx-auto mt-12">
      <Card>
        <CardContent className="py-12">
          <div className="flex flex-col items-center text-center gap-5">
            <div className="p-4 rounded-xl bg-[var(--color-surface-2)] border border-[var(--color-border)]">
              <Icon className="w-10 h-10 text-[var(--color-accent)]" />
            </div>
            <div className="space-y-2">
              <div className="flex items-center justify-center gap-2">
                <h2 className="text-lg font-bold text-[var(--color-text-primary)]">
                  {title}
                </h2>
                <Badge variant="warning">
                  <Construction className="w-3 h-3" />
                  {phase}
                </Badge>
              </div>
              <p className="text-sm text-[var(--color-text-secondary)] max-w-md">
                {description}
              </p>
            </div>
            <div className="w-full max-w-sm mt-2">
              <p className="text-xs font-semibold uppercase tracking-wider text-[var(--color-text-muted)] mb-3 text-left">
                Planned features
              </p>
              <ul className="space-y-2">
                {features.map((f) => (
                  <li
                    key={f}
                    className="flex items-center gap-2 text-sm text-[var(--color-text-secondary)]"
                  >
                    <span className="w-1 h-1 rounded-full bg-[var(--color-accent)] shrink-0" />
                    {f}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

export function VideoLibraryPage() {
  return (
    <Placeholder
      icon={Video}
      title="Video Library"
      description="Upload and manage CCTV footage. Automatically extract metadata, generate thumbnails, and track processing status."
      phase="Phase 3"
      features={[
        'Upload MP4, MOV, AVI files (up to 500 MB)',
        'Automatic metadata extraction (duration, resolution, FPS)',
        'Thumbnail generation',
        'Processing status tracking',
        'Video preview and playback',
        'Safe video and data deletion',
      ]}
    />
  )
}

export function SearchPage() {
  return (
    <Placeholder
      icon={Search}
      title="AI Video Search"
      description="Search your CCTV footage using natural language. The AI parses your query, applies semantic search, and returns ranked results with timestamps."
      phase="Phase 8"
      features={[
        'Natural language search ("person with red bag after 2 PM")',
        'Object-based and attribute filtering',
        'Time range filtering',
        'Semantic similarity ranking',
        'Video clip previews with timestamps',
        'Evidence-based match explanations',
      ]}
    />
  )
}

export function InvestigationsPage() {
  return (
    <Placeholder
      icon={FolderSearch}
      title="Investigation Workspace"
      description="Open an investigation, review the event timeline, and use the AI copilot to drill into specific events across multiple cameras."
      phase="Phase 9"
      features={[
        'Video player with event markers',
        'Investigation timeline',
        'Evidence list and management',
        'AI investigation copilot',
        'Follow-up questions and related event retrieval',
        'Multi-camera correlation',
      ]}
    />
  )
}

export function ReportsPage() {
  return (
    <Placeholder
      icon={FileText}
      title="Reports & Evidence"
      description="Generate structured incident reports grounded in actual video analysis results. Export reports as PDF and download evidence clips."
      phase="Phase 10"
      features={[
        'AI-generated incident reports (grounded in video evidence)',
        'Evidence timeline with video clips',
        'Exportable PDF reports',
        'Downloadable evidence clips',
        'Report history and management',
      ]}
    />
  )
}

export function SettingsPage() {
  return (
    <Placeholder
      icon={Settings2}
      title="Settings"
      description="Configure cameras, storage, AI models, and notification preferences."
      phase="Phase 11"
      features={[
        'Camera management',
        'Storage configuration',
        'AI model selection',
        'API key management',
        'User preferences',
      ]}
    />
  )
}
