/**
 * Video service – typed client methods for the Video Library API.
 */
import type { AxiosProgressEvent } from 'axios'
import apiClient from './api'
import type { Video, VideoListParams, VideoStats, ExtractedFrame, DetectionEvent, ObjectTrack } from '@/types'

export const videoService = {
  /**
   * List videos with search and status filtering.
   */
  async listVideos(params: VideoListParams = {}): Promise<Video[]> {
    const res = await apiClient.get<Video[]>('/videos', { params })
    return res.data
  },

  /**
   * Enqueue or retry background video processing.
   */
  async processVideo(id: string): Promise<Video> {
    const res = await apiClient.post<Video>(`/videos/${id}/process`)
    return res.data
  },

  /**
   * Get list of extracted keyframes with timestamps for a video.
   */
  async getVideoFrames(id: string): Promise<ExtractedFrame[]> {
    const res = await apiClient.get<ExtractedFrame[]>(`/videos/${id}/frames`)
    return res.data
  },

  /**
   * Get summary metrics for the library header.
   */
  async getVideoStats(): Promise<VideoStats> {
    const res = await apiClient.get<VideoStats>('/videos/stats/summary')
    return res.data
  },

  /**
   * Get single video record by ID.
   */
  async getVideo(id: string): Promise<Video> {
    const res = await apiClient.get<Video>(`/videos/${id}`)
    return res.data
  },

  /**
   * Stream upload a CCTV footage file with real progress tracking.
   */
  async uploadVideo(
    file: File,
    cameraId?: string,
    onProgress?: (percent: number, loaded: number, total: number) => void,
    signal?: AbortSignal,
  ): Promise<Video> {
    const formData = new FormData()
    formData.append('file', file)
    if (cameraId) {
      formData.append('camera_id', cameraId)
    }

    const res = await apiClient.post<Video>('/videos/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      signal,
      onUploadProgress: (progressEvent: AxiosProgressEvent) => {
        if (progressEvent.total && onProgress) {
          const percent = Math.round((progressEvent.loaded * 100) / progressEvent.total)
          onProgress(percent, progressEvent.loaded, progressEvent.total)
        }
      },
    })
    return res.data
  },

  /**
   * Delete a video and its stored files.
   */
  async deleteVideo(id: string): Promise<void> {
    await apiClient.delete(`/videos/${id}`)
  },

  /**
   * Returns streaming endpoint URL for HTML5 `<video>` source.
   */
  getStreamUrl(id: string): string {
    return `/api/v1/videos/${id}/stream`
  },

  /**
   * Returns thumbnail endpoint URL.
   */
  getThumbnailUrl(id: string): string {
    return `/api/v1/videos/${id}/thumbnail`
  },

  /**
   * Get all YOLO detection events for a video with optional class filtering.
   */
  async getVideoDetections(
    id: string,
    params?: { class_name?: string; min_confidence?: number; track_id?: string },
  ): Promise<DetectionEvent[]> {
    const res = await apiClient.get<DetectionEvent[]>(`/videos/${id}/detections`, { params })
    return res.data
  },

  /**
   * Get all continuous ByteTrack object tracks for a video.
   */
  async getVideoTracks(
    id: string,
    params?: { object_class?: string; min_confidence?: number },
  ): Promise<ObjectTrack[]> {
    const res = await apiClient.get<ObjectTrack[]>(`/videos/${id}/tracks`, { params })
    return res.data
  },

  /**
   * Get single track details with all associated detection events.
   */
  async getTrackDetail(id: string, trackId: string): Promise<ObjectTrack> {
    const res = await apiClient.get<ObjectTrack>(`/videos/${id}/tracks/${trackId}`)
    return res.data
  },

  /**
   * Returns annotated frame preview URL with bounding boxes drawn.
   */
  getAnnotatedFrameUrl(id: string, frameFilename: string): string {
    return `/api/v1/videos/${id}/frames/${frameFilename}/annotated`
  },
}
