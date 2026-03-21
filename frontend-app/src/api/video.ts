import { apiPost, apiGet } from './client'
import type {
  VideoGenerateAllResponse, VideoScenesResponse, FinalizeResponse,
} from '../types/api'

export const generateAllVideos = (project_id: string) =>
  apiPost<VideoGenerateAllResponse>('api/video/generate-all', { project_id })

export const getVideoScenes = (project_id: string) =>
  apiGet<VideoScenesResponse>(`api/video/${project_id}/scenes`)

export const finalizeVideo = (project_id: string) =>
  apiPost<FinalizeResponse>(`api/video/finalize/${project_id}`)

export const generateSingleVideo = (scene_id: string) =>
  apiPost<{ scene_id: string; video_url: string; video_status: string }>(
    'api/video',
    { scene_id }
  )
