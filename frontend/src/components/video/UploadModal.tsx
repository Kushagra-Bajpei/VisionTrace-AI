/**
 * UploadModal – Drag & Drop video upload modal with real chunked upload progress,
 * format validation, size limit checks, and cancellation support.
 */
import { useState, useRef, type DragEvent, type ChangeEvent } from 'react'
import {
  UploadCloud,
  FileVideo,
  AlertCircle,
  CheckCircle2,
  X,
  RefreshCw,
  HardDrive,
} from 'lucide-react'
import { Modal } from '@/components/ui/Modal'
import { Button } from '@/components/ui/Button'
import { ProgressBar } from '@/components/ui/Loading'
import { Badge } from '@/components/ui/Badge'
import { videoService } from '@/services/video'
import { formatBytes } from '@/lib/utils'

interface UploadModalProps {
  isOpen: boolean
  onClose: () => void
  onSuccess: () => void
}

const ALLOWED_EXTS = ['.mp4', '.mov', '.avi']
const MAX_BYTES = 500 * 1024 * 1024 // 500 MB

export function UploadModal({ isOpen, onClose, onSuccess }: UploadModalProps) {
  const [file, setFile] = useState<File | null>(null)
  const [isDragging, setIsDragging] = useState(false)
  const [isUploading, setIsUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [loadedBytes, setLoadedBytes] = useState(0)
  const [totalBytes, setTotalBytes] = useState(0)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [isSuccess, setIsSuccess] = useState(false)

  const abortControllerRef = useRef<AbortController | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const resetState = () => {
    setFile(null)
    setIsDragging(false)
    setIsUploading(false)
    setUploadProgress(0)
    setLoadedBytes(0)
    setTotalBytes(0)
    setErrorMessage(null)
    setIsSuccess(false)
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
      abortControllerRef.current = null
    }
  }

  const handleClose = () => {
    if (isUploading) {
      const confirmClose = window.confirm('Upload is in progress. Are you sure you want to cancel?')
      if (!confirmClose) return
      if (abortControllerRef.current) {
        abortControllerRef.current.abort()
      }
    }
    resetState()
    onClose()
  }

  const validateAndSelectFile = (selectedFile: File) => {
    setErrorMessage(null)
    const ext = `.${selectedFile.name.split('.').pop()?.toLowerCase()}`

    if (!ALLOWED_EXTS.includes(ext)) {
      setErrorMessage(`Unsupported format '${ext}'. Please upload an MP4, MOV, or AVI file.`)
      return
    }

    if (selectedFile.size > MAX_BYTES) {
      setErrorMessage(
        `File size (${formatBytes(selectedFile.size)}) exceeds maximum limit of 500 MB.`,
      )
      return
    }

    setFile(selectedFile)
  }

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setIsDragging(false)
    if (isUploading) return

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      validateAndSelectFile(e.dataTransfer.files[0])
    }
  }

  const handleDragOver = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    if (!isUploading) setIsDragging(true)
  }

  const handleDragLeave = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setIsDragging(false)
  }

  const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      validateAndSelectFile(e.target.files[0])
    }
  }

  const handleStartUpload = async () => {
    if (!file || isUploading) return

    setIsUploading(true)
    setErrorMessage(null)
    setUploadProgress(0)

    abortControllerRef.current = new AbortController()

    try {
      await videoService.uploadVideo(
        file,
        undefined,
        (percent, loaded, total) => {
          setUploadProgress(percent)
          setLoadedBytes(loaded)
          setTotalBytes(total)
        },
        abortControllerRef.current.signal,
      )

      setIsSuccess(true)
      setIsUploading(false)
      setTimeout(() => {
        onSuccess()
        handleClose()
      }, 1200)
    } catch (err: unknown) {
      setIsUploading(false)
      if (err instanceof Error && err.name === 'CanceledError') {
        setErrorMessage('Upload cancelled by user.')
      } else {
        const msg = err instanceof Error ? err.message : 'Upload failed. Check server status.'
        setErrorMessage(msg)
      }
    }
  }

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      title="Ingest CCTV Footage"
      subtitle="Upload recorded surveillance video to the forensic repository"
      maxWidth="xl"
    >
      <div className="space-y-5">
        {/* Drag & Drop Zone */}
        {!file && (
          <div
            onDrop={handleDrop}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onClick={() => fileInputRef.current?.click()}
            className={`flex flex-col items-center justify-center p-8 rounded-xl border-2 border-dashed transition-all duration-150 cursor-pointer ${
              isDragging
                ? 'border-[var(--color-accent)] bg-[var(--color-accent-subtle)] shadow-[0_0_20px_rgba(0,229,255,0.15)]'
                : 'border-[var(--color-border-2)] bg-[var(--color-surface-2)]/40 hover:border-[var(--color-accent)] hover:bg-[var(--color-surface-2)]'
            }`}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".mp4,.mov,.avi"
              className="hidden"
              onChange={handleFileChange}
            />
            <div className="p-3.5 rounded-full bg-[var(--color-surface-3)] border border-[var(--color-border-2)] text-[var(--color-accent)] mb-3 shadow-inner">
              <UploadCloud className="w-7 h-7" />
            </div>
            <p className="text-xs font-mono font-semibold text-[var(--color-text-primary)] uppercase tracking-wide">
              Drag & Drop footage or click to browse
            </p>
            <p className="text-[11px] text-[var(--color-text-secondary)] mt-1">
              Supports MP4, MOV, and AVI surveillance files up to 500 MB
            </p>

            <div className="flex items-center gap-2 mt-4">
              <Badge variant="telemetry">MP4</Badge>
              <Badge variant="telemetry">MOV</Badge>
              <Badge variant="telemetry">AVI</Badge>
              <Badge variant="telemetry">MAX 500 MB</Badge>
            </div>
          </div>
        )}

        {/* Selected File State */}
        {file && !isSuccess && (
          <div className="p-4 rounded-xl border border-[var(--color-border-2)] bg-[var(--color-surface-2)] space-y-4">
            <div className="flex items-start justify-between gap-3">
              <div className="flex items-center gap-3 min-w-0">
                <div className="p-2.5 rounded-lg bg-[var(--color-surface-3)] border border-[var(--color-border)] text-[var(--color-accent)] shrink-0">
                  <FileVideo className="w-5 h-5" />
                </div>
                <div className="min-w-0">
                  <p className="text-xs font-mono font-bold text-[var(--color-text-primary)] truncate">
                    {file.name}
                  </p>
                  <p className="text-[11px] font-mono text-[var(--color-text-secondary)] mt-0.5">
                    {formatBytes(file.size)} • {file.type || 'video/mp4'}
                  </p>
                </div>
              </div>

              {!isUploading && (
                <Button
                  variant="ghost"
                  size="icon-sm"
                  onClick={() => setFile(null)}
                  aria-label="Remove selected file"
                  className="text-[var(--color-text-muted)] hover:text-white"
                >
                  <X className="w-4 h-4" />
                </Button>
              )}
            </div>

            {/* Progress Bar during upload */}
            {isUploading && (
              <div className="space-y-2 pt-2 border-t border-[var(--color-border)]">
                <ProgressBar
                  percent={uploadProgress}
                  label="STREAMING FOOTAGE TO STORAGE"
                  sublabel={`${uploadProgress}% (${formatBytes(loadedBytes)} / ${formatBytes(totalBytes || file.size)})`}
                />
              </div>
            )}
          </div>
        )}

        {/* Success Feedback */}
        {isSuccess && (
          <div className="flex flex-col items-center justify-center p-6 rounded-xl border border-emerald-500/30 bg-emerald-950/20 text-center gap-2">
            <CheckCircle2 className="w-8 h-8 text-emerald-400" />
            <h4 className="text-xs font-mono uppercase font-bold text-emerald-300">
              Footage Ingested Successfully
            </h4>
            <p className="text-[11px] text-[var(--color-text-secondary)]">
              Metadata extracted and indexed into the surveillance database.
            </p>
          </div>
        )}

        {/* Error Feedback */}
        {errorMessage && (
          <div className="flex items-start gap-2.5 p-3 rounded-lg border border-rose-500/30 bg-rose-950/20 text-xs text-rose-300">
            <AlertCircle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
            <span className="leading-relaxed">{errorMessage}</span>
          </div>
        )}

        {/* Footer Actions */}
        <div className="flex items-center justify-between pt-3 border-t border-[var(--color-border)]">
          <div className="flex items-center gap-1.5 text-[11px] text-[var(--color-text-muted)] font-mono">
            <HardDrive className="w-3.5 h-3.5" />
            <span>Local Storage Repository</span>
          </div>

          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={handleClose}
              disabled={isUploading}
            >
              Cancel
            </Button>

            {file && !isSuccess && (
              <Button
                variant="primary"
                size="sm"
                onClick={handleStartUpload}
                disabled={isUploading}
              >
                {isUploading ? (
                  <>
                    <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                    <span>Uploading…</span>
                  </>
                ) : (
                  <span>Start Ingestion</span>
                )}
              </Button>
            )}
          </div>
        </div>
      </div>
    </Modal>
  )
}
